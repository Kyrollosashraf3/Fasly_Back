"""Database layer: engine, session factory and the shared declarative Base.

There is no migration tool in this project - the ORM models are the schema.
``create_tables()`` builds anything that does not exist yet on startup; a
column added to a model on a database that already exists is applied once
with ``ALTER TABLE <table> ADD COLUMN <column>`` (see the README).
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

logger.info("Creating SQLAlchemy engine for the configured database")
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db():
    """Yield one DB session per request (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns() -> None:
    """Add columns that exist on ORM models but are missing from an already
    created table (no migration tool is used in this project).

    ``ADD COLUMN IF NOT EXISTS`` is a no-op when the column is already there,
    so this is safe to run on every startup.
    """
    statements = [
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS note VARCHAR",
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS date DATE",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info("Missing-column check complete")


#: The CHECK expression exactly as ``app/models/user.py`` declares it.
_ROLE_OWNER_CHECK = (
    "(role IN ('teacher', 'admin') AND teacher_id IS NOT NULL AND boy_id IS NULL)"
    " OR (role = 'user' AND boy_id IS NOT NULL AND teacher_id IS NULL)"
    " OR (role = 'general_admin' AND teacher_id IS NOT NULL AND boy_id IS NULL)"
    " OR (role = 'super_admin' AND boy_id IS NULL)"
)


def _add_role_labels() -> None:
    """Add role labels the ORM knows but an existing ``role_enum`` does not.

    Postgres refuses to *use* a freshly added enum label in the same
    transaction, so this runs alone and commits before the constraint patch
    below quotes the new value.
    """
    with engine.begin() as conn:
        conn.execute(text("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'general_admin'"))
    logger.info("Role enum labels are up to date")


def _patch_role_owner_constraint() -> None:
    """Rebuild ``ck_users_role_owner`` so it knows the stage-amin role.

    ``create_all`` never alters an existing table, so a database that already
    has the constraint keeps the old wording; it is dropped and re-added from
    the same expression the model declares. Re-adding is a no-op when the
    stored definition already matches.
    """
    statements = [
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role_owner",
        "ALTER TABLE users ADD CONSTRAINT ck_users_role_owner "
        f"CHECK ({_ROLE_OWNER_CHECK})",
    ]
    with engine.begin() as conn:
        stored = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_users_role_owner'"
            )
        ).scalar()
        if stored is not None and "general_admin" in stored and stored.count("teacher_id IS NOT NULL") >= 2:
            return
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info("Account owner constraint now covers the stage-amin role")


def _rebuild_legacy_general_admin_classes() -> None:
    """Drop the stage amin's class table when it still keys the login.

    The group moved onto the servant (``teacher_id``) so it survives a phone or
    password change; the old ``user_id`` shape cannot be altered in place, and it
    never held real data, so it is dropped here and rebuilt by ``create_all``.
    """
    with engine.begin() as conn:
        legacy = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'general_admin_classes' AND column_name = 'user_id'"
            )
        ).scalar()
        if not legacy:
            return
        conn.execute(text("DROP TABLE IF EXISTS general_admin_classes"))
    logger.info("Stage-amin class table dropped; it is rebuilt keyed on the servant")


def create_tables() -> None:
    """Create every table the ORM declares that does not exist yet.

    Importing ``app.models`` first guarantees every model is registered on
    ``Base.metadata``, no matter which module the server was started from.
    """
    from app import models  # noqa: F401  (registers the ORM on Base.metadata)

    _rebuild_legacy_general_admin_classes()
    Base.metadata.create_all(bind=engine)
    _add_role_labels()
    _patch_role_owner_constraint()
    _add_missing_columns()
    logger.info(
        "Database tables are ready: %s", ", ".join(sorted(Base.metadata.tables))
    )