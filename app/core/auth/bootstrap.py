"""Seeds the first super admin, the default classes and the curated list of
church admins (أبونا) on startup.

``ADMIN_PHONE`` always wins: the platform owner is never downgraded to a
church admin, even when the same number appears in ``SEED_SUPER_ADMINS_JSON``.
"""

import json
from datetime import date
import re

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.core.data.common import default_church_id
from app.db.database import SessionLocal
from app.features.church.models.church import Church
from app.models.enums import RoleEnum
from app.features.school_class.models.school_class import SchoolClass
from app.features.teacher.models.teacher import Teacher
from app.features.user.models.user import User
from app.features.school_class.schemas.school_class import CLASS_NAMES
from app.features.user.schemas.user import PHONE_PATTERN, normalise_phone

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
    renamed or removed a class keeps their own catalogue. Every seeded class
    belongs to the configured default church.
    """
    db = SessionLocal()
    try:
        if db.query(SchoolClass.id).first() is not None:
            return
        church_id = default_church_id(db)
        year = current_academic_year()
        for name in DEFAULT_CLASS_NAMES:
            db.add(
                SchoolClass(name=name, academic_year=year, church_id=church_id)
            )
        db.commit()
        logger.info(
            "Seeded %d default classes for %s (church id=%d)",
            len(DEFAULT_CLASS_NAMES),
            year,
            church_id,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to seed default classes")
        raise
    finally:
        db.close()


def _bootstrap_phone() -> str | None:
    """Normalised ``ADMIN_PHONE``, or ``None`` when unset / not a phone."""
    raw = settings.ADMIN_PHONE
    if not raw:
        return None
    phone = str(normalise_phone(str(raw).strip()))
    return phone if re.fullmatch(PHONE_PATTERN, phone) else None


def ensure_bootstrap_admin() -> None:
    """Create - and repair - the platform owner on every startup.

    Controlled by ADMIN_PHONE in the environment (ADMIN_PASSWORD is only needed
    the first time, to create the account). The account is the platform owner:
    it stays a ``super_admin`` with no church and no owner row so it can see
    every tenant. A legacy church-admin seed may have downgraded it (or
    attached a servant row); that is undone here, which makes repeated deploys
    idempotent instead of silently flipping the role back.
    """
    if not settings.ADMIN_PHONE:
        logger.info("Bootstrap admin skipped (ADMIN_PHONE not set)")
        return

    phone = _bootstrap_phone()
    if phone is None:
        logger.warning(
            "Bootstrap admin skipped (ADMIN_PHONE '%s' is not a phone)",
            settings.ADMIN_PHONE,
        )
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing is not None:
            changed = False
            if existing.role != RoleEnum.SUPER_ADMIN:
                existing.role = RoleEnum.SUPER_ADMIN
                changed = True
            # super_admin owns no church and no person - clear any leftovers
            # the church-admin seed attached so the role and the row agree.
            for field in ("church_id", "teacher_id", "boy_id"):
                if getattr(existing, field) is not None:
                    setattr(existing, field, None)
                    changed = True
            if changed:
                db.commit()
                logger.info(
                    "Bootstrap admin restored to super_admin: %s (id=%d)",
                    phone,
                    existing.id,
                )
            return

        if not settings.ADMIN_PASSWORD:
            logger.info("Bootstrap admin creation skipped (ADMIN_PASSWORD not set)")
            return

        admin = User(
            phone=phone,
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            role=RoleEnum.SUPER_ADMIN,
            church_id=None,
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


def _seed_church_id(db, entry: dict) -> int:
    """Church of a seed entry: explicit id, else name, else the default."""
    church_id = entry.get("church_id")
    if church_id is not None:
        return int(church_id)
    name = entry.get("church") or entry.get("church_name")
    if name:
        church = db.query(Church).filter(Church.name == str(name).strip()).first()
        if church is not None:
            return church.id
        logger.warning(
            "Church seed %r not found for %r; using the default church",
            name,
            entry.get("phone"),
        )
    return default_church_id(db)


def ensure_seeded_super_admins() -> None:
    """Create the church admins listed in ``SEED_SUPER_ADMINS_JSON``.

    The historical name is kept for compatibility with the startup caller.
    Each entry ``{"name", "phone", "church" | "church_id"}`` becomes a servant
    with no class and an ``abona`` login tied to one church - the amin who sees
    every class of his church and nothing outside it.

    Idempotent: a phone is never duplicated. A legacy ``super_admin`` that was
    seeded here (it has a servant row) is converted to ``abona`` and assigned
    its church. The one exception is ``ADMIN_PHONE``: that is the platform
    owner, so the entry is skipped entirely and he stays ``super_admin`` even
    when the same number is listed here by mistake.
    """
    raw = settings.SEED_SUPER_ADMINS_JSON
    if not raw:
        logger.info("Church-admin seed skipped (SEED_SUPER_ADMINS_JSON not set)")
        return
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "Church-admin seed skipped (SEED_SUPER_ADMINS_JSON is not valid JSON)"
        )
        return
    if not isinstance(entries, list) or not entries:
        logger.info("Church-admin seed skipped (empty list)")
        return

    db = SessionLocal()
    owner_phone = _bootstrap_phone()
    try:
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            phone = entry.get("phone")
            if not name or not phone:
                logger.warning(
                    "Church-admin seed: skipped entry without name/phone: %r", entry
                )
                continue
            phone = str(normalise_phone(phone))
            if not re.fullmatch(PHONE_PATTERN, phone):
                logger.warning("Church-admin seed: skipped bad phone %r", phone)
                continue

            if owner_phone is not None and phone == owner_phone:
                logger.info(
                    "Church-admin seed: skipped platform owner %s (kept super_admin)",
                    phone,
                )
                continue

            church_id = _seed_church_id(db, entry)

            teacher = (
                db.query(Teacher).filter(Teacher.phone == phone).first()
                or db.query(Teacher)
                .filter(Teacher.teacher_name == name, Teacher.phone == phone)
                .first()
            )
            if teacher is None:
                # A church amin does not belong to one class - the servant row
                # is filed with NULL so he sees every class of his church.
                teacher = Teacher(
                    teacher_name=name,
                    phone=phone,
                    class_id=None,
                    church_id=church_id,
                )
                db.add(teacher)
                db.flush()
                logger.info("Church-admin seed: created servant %s (%s)", name, phone)
            elif teacher.church_id is None:
                teacher.church_id = church_id

            user = db.query(User).filter(User.phone == phone).first()
            if user is None:
                user = User(
                    phone=phone,
                    role=RoleEnum.ABONA,
                    teacher_id=teacher.id,
                    church_id=church_id,
                )
                db.add(user)
                db.flush()
                logger.info(
                    "Church-admin seed: created login %s -> servant %s", phone, name
                )
            elif user.role == RoleEnum.SUPER_ADMIN and user.teacher_id is not None:
                # A previously seeded church-wide admin: he was never the
                # platform owner (that account has no servant row).
                user.role = RoleEnum.ABONA
                user.church_id = church_id
                logger.info(
                    "Church-admin seed: converted %s to abona in church %d",
                    phone,
                    church_id,
                )
            elif user.role == RoleEnum.ABONA and user.church_id is None:
                user.church_id = church_id

            if user.teacher_id != teacher.id:
                user.teacher_id = teacher.id
                logger.info(
                    "Church-admin seed: attached servant %s to login %s", name, phone
                )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to seed church admins")
        raise
    finally:
        db.close()


#: Readable alias used by newer callers.
ensure_seeded_church_admins = ensure_seeded_super_admins
