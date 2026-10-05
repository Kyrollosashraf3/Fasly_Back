from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.schema import CreateColumn

from app.config.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

logger.info("Creating SQLAlchemy engine for the configured database")
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Every table the ORM owns - created on startup by init_db().
ALL_TABLES = [
    "classes",
    "users",
    "boys",
    "teachers",
    "groups",
    "attends",
    "follow_ups",
    "teacher_checks",
]


def get_db():
    """Yield a DB session per request (FastAPI dependency)."""
    db = SessionLocal()
    logger.debug("DB session opened")
    try:
        yield db
    finally:
        logger.debug("DB session closed")
        db.close()


def ensure_columns() -> dict[str, list[str]]:
    """Add every column the ORM defines but the live table is missing.

    ``create_all()`` only creates whole tables, so a column added to an
    existing model (e.g. ``teachers.last_visit_date``) never appears on a
    database created before that change. Only additive ``ALTER TABLE ...
    ADD COLUMN`` statements are issued here - nothing is dropped, retyped or
    narrowed. A NOT NULL column without a server default is skipped and
    logged, because PostgreSQL cannot apply it automatically.
    """
    from app import models  # noqa: F401  (registers the ORM on Base.metadata)

    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    added: dict[str, list[str]] = {}

    for table in Base.metadata.sorted_tables:
        if table.name not in present:
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            if (
                not column.nullable
                and column.server_default is None
                and not column.primary_key
            ):
                logger.warning(
                    "Cannot auto-add %s.%s: NOT NULL without a default. "
                    "Add it manually.",
                    table.name,
                    column.name,
                )
                continue
            ddl = (
                f'ALTER TABLE "{table.name}" ADD COLUMN '
                f"{CreateColumn(column).compile(engine)}"
            )
            logger.info("Applying schema change: %s", ddl)
            with engine.begin() as conn:
                conn.exec_driver_sql(ddl)
            added.setdefault(table.name, []).append(column.name)

    if added:
        logger.info("Columns added: %s", added)
    return added


# Columns this ORM no longer declares, so a database created before the
# change is brought in line with the model. Only columns listed here are
# ever dropped - nothing else in the schema is touched.
RETIRED_COLUMNS = {
    "classes": ["grade_number"],
    "users": ["email"],
}


def drop_retired_columns() -> list[str]:
    """Drop columns the ORM used to declare but no longer does.

    ``ensure_columns()`` only ever adds, so a removed column would otherwise
    sit in the live table forever. PostgreSQL drops the indexes and table
    constraints that involve the column along with it.
    """
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    dropped: list[str] = []

    for table, columns in RETIRED_COLUMNS.items():
        if table not in present:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for column in columns:
            if column not in existing:
                continue
            ddl = f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
            logger.info("Applying schema change: %s", ddl)
            with engine.begin() as conn:
                conn.exec_driver_sql(ddl)
            dropped.append(f"{table}.{column}")

    if dropped:
        logger.info("Columns dropped: %s", dropped)
    return dropped


# Columns the model declares as nullable but the live table still carries as
# NOT NULL (e.g. ``users.password_hash`` before self-service signup). Relaxing
# is always safe - it only ever permits NULL - and PostgreSQL needs an explicit
# statement for it.
RELAXED_COLUMNS = {
    "users": ["password_hash"],
}


def relax_columns() -> list[str]:
    """Drop the NOT NULL flag from the columns listed in RELAXED_COLUMNS."""
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    relaxed: list[str] = []

    for table, columns in RELAXED_COLUMNS.items():
        if table not in present:
            continue
        existing = {col["name"]: col for col in inspector.get_columns(table)}
        for column in columns:
            info = existing.get(column)
            if info is None or info.get("nullable", True):
                continue
            ddl = f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL'
            logger.info("Applying schema change: %s", ddl)
            with engine.begin() as conn:
                conn.exec_driver_sql(ddl)
            relaxed.append(f"{table}.{column}")

    if relaxed:
        logger.info("Columns relaxed: %s", relaxed)
    return relaxed


# Columns the model declares NOT NULL but a live table still allows NULL on
# (the column existed before the constraint was added). The offending rows are
# removed first by purge_unusable_rows(), then the flag is applied.
REQUIRED_COLUMNS = {
    "users": ["phone"],
}


def purge_unusable_rows() -> int:
    """Delete rows that would violate a REQUIRED_COLUMNS invariant.

    A login without a phone number cannot authenticate at all any more - the
    handle is the phone - and it breaks ``GET /auth/users`` on the way.
    """
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    removed = 0

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in present:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for column in columns:
            if column not in existing:
                continue
            with engine.begin() as conn:
                result = conn.exec_driver_sql(
                    f'DELETE FROM "{table}" WHERE "{column}" IS NULL '
                    f"OR \"{column}\" = ''"
                )
            if result.rowcount:
                logger.warning(
                    "Removed %d row(s) from '%s' with no '%s' "
                    "(cannot be used any more).",
                    result.rowcount,
                    table,
                    column,
                )
                removed += result.rowcount

    return removed


def tighten_columns() -> list[str]:
    """Apply the NOT NULL flag the model declares, after the purge."""
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    tightened: list[str] = []

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in present:
            continue
        existing = {col["name"]: col for col in inspector.get_columns(table)}
        for column in columns:
            info = existing.get(column)
            if info is None or not info.get("nullable", True):
                continue
            ddl = f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL'
            logger.info("Applying schema change: %s", ddl)
            with engine.begin() as conn:
                conn.exec_driver_sql(ddl)
            tightened.append(f"{table}.{column}")

    if tightened:
        logger.info("Columns tightened: %s", tightened)
    return tightened


def init_db() -> dict[str, str]:
    """Create any missing table, then report the state of every one.

    Mirrors the old ``ensure_collections()`` startup check: the log tells you
    which tables are ready. Importing ``app.models`` here guarantees every
    ORM class is registered on ``Base.metadata`` before ``create_all`` runs,
    no matter which module the server was started from.
    """
    from app import models  # noqa: F401  (registers the ORM on Base.metadata)

    Base.metadata.create_all(bind=engine)
    ensure_columns()
    drop_retired_columns()
    relax_columns()
    purge_unusable_rows()
    tighten_columns()
    existing = set(inspect(engine).get_table_names())
    status: dict[str, str] = {}
    for name in ALL_TABLES:
        status[name] = "ready" if name in existing else "missing"
        logger.info("Table '%s': %s", name, status[name])
    missing = [name for name, state in status.items() if state == "missing"]
    if missing:
        raise RuntimeError(
            f"Database is not initialized, missing tables: {missing}. "
            "Run the app once against an empty database or apply the schema manually."
        )
    logger.info("Database tables are ready")
    return status
