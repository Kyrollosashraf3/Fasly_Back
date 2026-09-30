"""Seeds the first super admin on startup when configured via env vars."""

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.database import SessionLocal
from app.models.enums import RoleEnum
from app.models.user import User

logger = get_logger(__name__)


def ensure_bootstrap_admin() -> None:
    """Create the first super admin if it does not exist.

    Controlled by ADMIN_MAIL / ADMIN_PASSWORD in the environment.

    The account is seeded as ``super_admin`` on purpose: every other role must
    be attached to an existing servant or boy (``ck_users_role_owner``), and on
    a brand new database neither exists yet. From this account the first class,
    servant, boy and ordinary logins are created.

    Safe to call on every startup: it is a no-op once the email is taken.
    """
    if not settings.ADMIN_MAIL or not settings.ADMIN_PASSWORD:
        logger.info("Bootstrap admin skipped (ADMIN_MAIL/ADMIN_PASSWORD not set)")
        return

    db = SessionLocal()
    try:
        email = settings.ADMIN_MAIL.strip().lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            return

        admin = User(
            email=email,
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            role=RoleEnum.SUPER_ADMIN,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Bootstrap super admin created: %s (id=%d)", admin.email, admin.id)
    except Exception:
        db.rollback()
        logger.exception("Failed to create bootstrap admin")
        raise
    finally:
        db.close()
