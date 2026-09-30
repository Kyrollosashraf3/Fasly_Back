"""Seeds the first admin account on startup when configured via env vars."""

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.database import SessionLocal
from app.models.enums import RoleEnum
from app.models.user import User

logger = get_logger(__name__)


def ensure_bootstrap_admin() -> None:
    """Create the first admin user if it does not exist.

    Controlled by ADMIN_MAIL / ADMIN_PASSWORD in the environment.
    Safe to call on every startup: it is a no-op once an admin exists.
    """
    if not settings.ADMIN_MAIL or not settings.ADMIN_PASSWORD:
        logger.info("Bootstrap admin skipped (ADMIN_MAIL/ADMIN_PASSWORD not set)")
        return

    db = SessionLocal()
    try:
        existing = (
            db.query(User)
            .filter(User.mail == settings.ADMIN_MAIL, User.role == RoleEnum.ADMIN)
            .first()
        )
        if existing is not None:
            return

        admin = User(
            user_name=settings.ADMIN_USER_NAME,
            mail=settings.ADMIN_MAIL,
            phone=None,
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            role=RoleEnum.ADMIN,
            class_name=None,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info(f"Bootstrap admin created: {admin.mail} (id={admin.id})")
    except Exception:
        db.rollback()
        logger.exception("Failed to create bootstrap admin")
        raise
    finally:
        db.close()
