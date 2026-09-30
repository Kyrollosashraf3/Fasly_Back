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
