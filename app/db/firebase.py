from firebase_admin import credentials, firestore

import firebase_admin

from app.config.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

logger.info("Creating Firestore client for the configured Firebase project")

_client = None


def init_firebase():
    """Create (once) and return the Firestore client. Mirrors create_engine()."""
    global _client

    if _client is not None:
        return _client

    if settings.SERVICE_ACCOUNT is None:
        logger.warning(
            "No credentials found - set FIREBASE_CREDENTIALS_JSON (Render) "
            "or FIREBASE_CREDENTIALS to a valid file path (local, e.g. ./test.json)"
        )
        return None

    service_account = settings.SERVICE_ACCOUNT
    cred = credentials.Certificate(service_account)

    # Avoid "default app already exists" on reload / repeated startup
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass  # default app already exists

    _client = firestore.client()
    logger.info(
        "Firestore client created successfully. project: %s",
        settings.SERVICE_ACCOUNT.get("project_id"),
    )
    return _client


# Singleton connection object — mirrors `engine` in database.py
db = init_firebase()


def ensure_collections() -> dict[str, str]:
    """Check every collection at startup (mirrors create_all()).

    Firestore is schemaless: a collection physically appears only after the
    first document is written, so there is no "CREATE TABLE". Instead we verify
    each collection is reachable and log whether it already holds data or will
    be created on first write.
    """
    client = _client if _client is not None else init_firebase()
    if client is None:
        raise ConnectionError(
            "Firebase not connected: set FIREBASE_CREDENTIALS_JSON env var "
            "(Render) or make sure the FIREBASE_CREDENTIALS file exists locally"
        )
    status: dict[str, str] = {}
    for name in settings.ALL_COLLECTIONS:
        try:
            has_docs = len(list(client.collection(name).limit(1).stream())) > 0
        except Exception as exc:
            logger.error("Collection '%s' is not reachable: %s", name, exc)
            raise
        status[name] = "exists" if has_docs else "empty (will be created on first write)"
        logger.info("Collection '%s': %s", name, status[name])
    return status


def get_db():
    """Yield the Firestore client per-request. Mirrors database.py get_db()."""
    client = _client if _client is not None else init_firebase()
    if client is None:
        raise ConnectionError(
            "Firebase not connected: set FIREBASE_CREDENTIALS_JSON env var "
            "(Render) or make sure the FIREBASE_CREDENTIALS file exists locally"
        )
    logger.debug("Firestore client yielded")
    try:
        yield client
    finally:
        # Firestore is a shared singleton — nothing to close per request.
        # Kept try/finally to match database.py structure.
        logger.debug("Firestore request finished")
