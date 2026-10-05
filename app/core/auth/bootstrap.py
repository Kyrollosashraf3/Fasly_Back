"""Seeds the first super admin and the default classes on startup."""

from datetime import date
import re

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.database import SessionLocal
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.user import User
from app.schemas.school_class import CLASS_NAMES
from app.schemas.user import PHONE_PATTERN, normalise_phone

logger = get_logger(__name__)

# A fresh database starts with the six primary classes; the rest of the fixed
# catalogue (إعدادي / ثانوي / شباب) is added from the class dialog.
DEFAULT_CLASS_NAMES = CLASS_NAMES[:6]


def current_academic_year(today: date | None = None) -> str:
    """``2026/2027`` from September, ``2025/2026`` before it."""
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}/{start + 1}"


def ensure_default_classes() -> None:
    """Seed the six default classes once, so a fresh database is usable.

    Only runs while the ``classes`` table is empty: an administrator who
    renamed or removed a class keeps their own catalogue.
    """
    db = SessionLocal()
    try:
        if db.query(SchoolClass.id).first() is not None:
            return
        year = current_academic_year()
        for name in DEFAULT_CLASS_NAMES:
            db.add(SchoolClass(name=name, academic_year=year))
        db.commit()
        logger.info("Seeded %d default classes for %s", len(DEFAULT_CLASS_NAMES), year)
    except Exception:
        db.rollback()
        logger.exception("Failed to seed default classes")
        raise
    finally:
        db.close()


def ensure_bootstrap_admin() -> None:
    """Create the first super admin if it does not exist.

    Controlled by ADMIN_PHONE / ADMIN_PASSWORD in the environment.

    The account is seeded as ``super_admin`` on purpose: every other role must
    be attached to an existing servant or boy (``ck_users_role_owner``), and on
    a brand new database neither exists yet. From this account the first class,
    servant, boy and ordinary logins are created.

    Safe to call on every startup: it is a no-op once the phone is taken.
    """
    if not settings.ADMIN_PHONE or not settings.ADMIN_PASSWORD:
        logger.info("Bootstrap admin skipped (ADMIN_PHONE/ADMIN_PASSWORD not set)")
        return

    phone = str(normalise_phone(settings.ADMIN_PHONE.strip()))
    if not re.fullmatch(PHONE_PATTERN, phone):
        logger.warning("Bootstrap admin skipped (ADMIN_PHONE '%s' is not a phone)", phone)
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing is not None:
            return

        admin = User(
            phone=phone,
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            role=RoleEnum.SUPER_ADMIN,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Bootstrap super admin created: %s (id=%d)", phone, admin.id)
    except Exception:
        db.rollback()
        logger.exception("Failed to create bootstrap admin")
        raise
    finally:
        db.close()
