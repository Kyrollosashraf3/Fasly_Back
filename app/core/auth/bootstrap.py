"""Seeds the first super admin and the default classes on startup."""

from datetime import date

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.database import SessionLocal
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.user import User

logger = get_logger(__name__)

GRADE_NAMES = {
    1: "الصف الأول",
    2: "الصف الثاني",
    3: "الصف الثالث",
    4: "الصف الرابع",
    5: "الصف الخامس",
    6: "الصف السادس",
}


def current_academic_year(today: date | None = None) -> str:
    """``2026/2027`` from September, ``2025/2026`` before it."""
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}/{start + 1}"


def ensure_default_classes() -> None:
    """Seed grades 1..6 once, so a fresh database is usable immediately.

    Only runs while the ``classes`` table is empty: an administrator who
    renamed or removed a class keeps their own catalogue.
    """
    db = SessionLocal()
    try:
        if db.query(SchoolClass.id).first() is not None:
            return
        year = current_academic_year()
        for grade, name in GRADE_NAMES.items():
            db.add(
                SchoolClass(
                    name=name, grade_number=grade, academic_year=year
                )
            )
        db.commit()
        logger.info("Seeded %d default classes for %s", len(GRADE_NAMES), year)
    except Exception:
        db.rollback()
        logger.exception("Failed to seed default classes")
        raise
    finally:
        db.close()


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
