from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

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
    "users",
    "boys",
    "teachers",
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


def init_db() -> dict[str, str]:
    """Create any missing table, then report the state of every one.

    Mirrors the old ``ensure_collections()`` startup check: the log tells you
    which tables are ready. Importing ``app.models`` here guarantees every
    ORM class is registered on ``Base.metadata`` before ``create_all`` runs,
    no matter which module the server was started from.
    """
    from app import models  # noqa: F401  (registers the ORM on Base.metadata)

    Base.metadata.create_all(bind=engine)
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
