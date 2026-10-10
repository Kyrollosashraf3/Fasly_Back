"""Seeds the first super admin, the default classes and the curated list of
church-wide admins on startup."""

import json
from datetime import date
import re

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.db.database import SessionLocal
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
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


def ensure_seeded_super_admins() -> None:
    """Create the church-wide admins listed in ``SEED_SUPER_ADMINS_JSON``.

    Each entry is ``{"name": "...", "phone": "..."}``. On every startup each
    entry ends up as a servant with **no class** (his scope is every class)
    and as a ``super_admin`` login linked to that servant, so the account
    has a name.

    Idempotent and additive: a phone already registered is never duplicated.
    When the login already exists the missing piece (the servant and/or the
    ``teacher_id`` link) is added; existing teachers of the same phone are
    reused.
    """
    raw = settings.SEED_SUPER_ADMINS_JSON
    if not raw:
        logger.info("Super-admin seed skipped (SEED_SUPER_ADMINS_JSON not set)")
        return
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "Super-admin seed skipped (SEED_SUPER_ADMINS_JSON is not valid JSON)"
        )
        return
    if not isinstance(entries, list) or not entries:
        logger.info("Super-admin seed skipped (empty list)")
        return

    db = SessionLocal()
    try:
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            phone = entry.get("phone")
            if not name or not phone:
                logger.warning(
                    "Super-admin seed: skipped entry without name/phone: %r", entry
                )
                continue
            phone = str(normalise_phone(phone))
            if not re.fullmatch(PHONE_PATTERN, phone):
                logger.warning("Super-admin seed: skipped bad phone %r", phone)
                continue

            teacher = (
                db.query(Teacher).filter(Teacher.phone == phone).first()
                or db.query(Teacher)
                .filter(Teacher.teacher_name == name, Teacher.phone == phone)
                .first()
            )
            if teacher is None:
                # A church-wide admin does not belong to one class - the
                # servant row is filed with NULL so he sees every class.
                teacher = Teacher(teacher_name=name, phone=phone, class_id=None)
                db.add(teacher)
                db.flush()
                logger.info("Super-admin seed: created servant %s (%s)", name, phone)

            user = db.query(User).filter(User.phone == phone).first()
            if user is None:
                user = User(
                    phone=phone, role=RoleEnum.SUPER_ADMIN, teacher_id=teacher.id
                )
                db.add(user)
                db.flush()
                logger.info(
                    "Super-admin seed: created login %s -> servant %s", phone, name
                )
            elif user.role != RoleEnum.SUPER_ADMIN:
                logger.warning(
                    "Super-admin seed: %s already exists with role %s - untouched",
                    phone,
                    user.role,
                )
            elif user.teacher_id != teacher.id:
                user.teacher_id = teacher.id
                logger.info(
                    "Super-admin seed: attached servant %s to login %s", name, phone
                )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to seed super admins")
        raise
    finally:
        db.close()
