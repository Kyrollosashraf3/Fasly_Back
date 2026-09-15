"""Seeds the first admin account on startup when configured via env vars."""

from datetime import datetime, timezone

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.firebase import init_firebase
from app.models.enums import RoleEnum

logger = get_logger(__name__)


def ensure_bootstrap_admin() -> None:
    """Create the first admin user if it does not exist.

    Controlled by ADMIN_MAIL / ADMIN_PASSWORD in the environment.
    Safe to call on every startup: it is a no-op once an admin exists.
    """
    if not settings.ADMIN_MAIL or not settings.ADMIN_PASSWORD:
        logger.info("Bootstrap admin skipped (ADMIN_MAIL/ADMIN_PASSWORD not set)")
        return

    client = init_firebase()
    if client is None:
        raise ConnectionError("Firebase not connected, cannot bootstrap admin")

    col = client.collection(settings.COLLECTION_USER)
    existing = list(
        col.where("mail", "==", settings.ADMIN_MAIL).where("role", "==", RoleEnum.ADMIN.value).limit(1).stream()
    )
    if existing:
        return

    _, doc_ref = col.add(
        {
            "user_name": settings.ADMIN_USER_NAME,
            "mail": settings.ADMIN_MAIL,
            "phone": None,
            "password_hash": get_password_hash(settings.ADMIN_PASSWORD),
            "role": RoleEnum.ADMIN.value,
            "class_name": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    logger.info(f"Bootstrap admin created: {settings.ADMIN_MAIL} (id={doc_ref.id})")
