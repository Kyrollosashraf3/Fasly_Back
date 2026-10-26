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


def create_tables() -> None:
    """Create every table the ORM declares that does not exist yet.

    Importing ``app.models`` first guarantees every model is registered on
    ``Base.metadata``, no matter which module the server was started from.
    """
    from app import models  # noqa: F401  (registers the ORM on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    logger.info(
        "Database tables are ready: %s", ", ".join(sorted(Base.metadata.tables))
    )