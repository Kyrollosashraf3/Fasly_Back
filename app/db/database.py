"""Database layer: engine, session factory and the shared declarative Base.

There is no migration tool in this project - the ORM models are the schema.
``create_tables()`` builds anything that does not exist yet on startup; a
column added to a model on a database that already exists is applied here with
``ALTER TABLE ... ADD COLUMN`` plus a backfill (see ``church.txt`` for the same
steps as plain SQL to run from pgAdmin).
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


#: Every data / log table that carries a ``church_id``. ``churches`` itself is
#: the tenant anchor and is deliberately not in this list.
TENANT_TABLES = (
    "users",
    "teachers",
    "boys",
    "classes",
    "groups",
    "general_admin_classes",
    "attends",
    "follow_ups",
    "teacher_follow_ups",
    "teacher_checks",
    "tasks",
    "task_values",
    "trips",
    "servant_trips",
    "trip_attendances",
    "teams",
    "team_members",
    "team_teachers",
    "subscriptions",
    "servant_trip_subscriptions",
    "notification_logs",
    "notification_inbox",
    "push_devices",
)


def _has_column(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
        is not None
    )


def _has_constraint(conn, table: str, name: str) -> bool:
    return (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_schema = current_schema() "
                "AND table_name = :t AND constraint_name = :c"
            ),
            {"t": table, "c": name},
        ).scalar()
        is not None
    )


def _add_missing_columns() -> None:
    """Add columns that exist on ORM models but are missing from an already
    created table (no migration tool is used in this project).
    """
    statements = [
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS note VARCHAR",
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS date DATE",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info("Missing-column check complete")


def _ensure_default_church() -> int:
    """Create the configured default tenant if it is not there yet."""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM churches WHERE name = :n ORDER BY id LIMIT 1"),
            {"n": settings.DEFAULT_CHURCH_NAME},
        ).first()
        if row is not None:
            return int(row[0])
        result = conn.execute(
            text(
                "INSERT INTO churches "
                "(name, region, address, phone, phone_2, is_active) "
                "VALUES (:n, :r, :a, :p, :p2, TRUE) RETURNING id"
            ),
            {
                "n": settings.DEFAULT_CHURCH_NAME,
                "r": settings.DEFAULT_CHURCH_REGION,
                "a": settings.DEFAULT_CHURCH_ADDRESS,
                "p": settings.DEFAULT_CHURCH_PHONE,
                "p2": settings.DEFAULT_CHURCH_PHONE_2,
            },
        )
        church_id = int(result.scalar_one())
    logger.info("Default church ready (id=%d)", church_id)
    return church_id


def _add_tenant_columns() -> None:
    """Add ``church_id`` (nullable at first) to every existing tenant table."""
    with engine.begin() as conn:
        for table in TENANT_TABLES:
            if not _has_column(conn, table, "church_id"):
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN church_id INTEGER")
                )
    logger.info("Tenant columns are present on all tables")


def _backfill_tenant_columns(default_church_id: int) -> None:
    """Point every legacy row at the default church.

    ``users.church_id`` stays NULL for the platform owner (``super_admin``),
    who by design belongs to no church; every other login gets the default.
    """
    with engine.begin() as conn:
        for table in TENANT_TABLES:
            if table == "users":
                conn.execute(
                    text(
                        "UPDATE users SET church_id = :id "
                        "WHERE church_id IS NULL AND role <> 'super_admin'"
                    ),
                    {"id": default_church_id},
                )
            else:
                conn.execute(
                    text(f"UPDATE {table} SET church_id = :id WHERE church_id IS NULL"),
                    {"id": default_church_id},
                )
    logger.info("Legacy rows backfilled to church id=%d", default_church_id)


def _add_tenant_constraints() -> None:
    """Add the tenant FKs and indexes if they are not there already.

    A fresh database gets them from ``create_all``; an existing one needs them
    added explicitly because ``create_all`` never alters a table.
    """
    with engine.begin() as conn:
        for table in TENANT_TABLES:
            fk = f"{table}_church_id_fkey"
            if not _has_constraint(conn, table, fk):
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD CONSTRAINT {fk} "
                        "FOREIGN KEY (church_id) REFERENCES churches(id) "
                        "ON DELETE RESTRICT"
                    )
                )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_church_id "
                    f"ON {table} (church_id)"
                )
            )
    logger.info("Tenant foreign keys and indexes are in place")


def _set_tenant_columns_not_null() -> None:
    """Make ``church_id`` required everywhere except ``users`` (owner is NULL)."""
    with engine.begin() as conn:
        for table in TENANT_TABLES:
            if table == "users":
                continue
            conn.execute(
                text(f"ALTER TABLE {table} ALTER COLUMN church_id SET NOT NULL")
            )
    logger.info("Tenant columns are NOT NULL")


def _rebuild_notification_dedupe() -> None:
    """Scope the scheduled-message dedupe key to a church.

    Two churches may each fire their own ``followup:YYYY-MM-DD`` on the same
    day, so the unique key becomes ``(church_id, dedupe_key)``. Manual rows keep
    a NULL key and stay allowed many times over (Postgres treats NULLs as
    distinct in a unique constraint).
    """
    with engine.begin() as conn:
        if _has_constraint(conn, "notification_logs", "uq_notification_logs_dedupe_key"):
            conn.execute(
                text(
                    "ALTER TABLE notification_logs "
                    "DROP CONSTRAINT uq_notification_logs_dedupe_key"
                )
            )
        if not _has_constraint(
            conn, "notification_logs", "uq_notification_logs_church_dedupe_key"
        ):
            conn.execute(
                text(
                    "ALTER TABLE notification_logs ADD CONSTRAINT "
                    "uq_notification_logs_church_dedupe_key "
                    "UNIQUE (church_id, dedupe_key)"
                )
            )
    logger.info("Notification dedupe key is church-scoped")


#: The CHECK expression exactly as ``app/features/user/models/user.py`` declares it.
_ROLE_OWNER_CHECK = (
    "(role IN ('teacher', 'admin') AND teacher_id IS NOT NULL"
    " AND boy_id IS NULL AND church_id IS NOT NULL)"
    " OR (role = 'user' AND boy_id IS NOT NULL AND teacher_id IS NULL"
    " AND church_id IS NOT NULL)"
    " OR (role = 'general_admin' AND teacher_id IS NOT NULL"
    " AND boy_id IS NULL AND church_id IS NOT NULL)"
    " OR (role = 'abona' AND boy_id IS NULL AND church_id IS NOT NULL)"
    " OR (role = 'super_admin' AND boy_id IS NULL)"
)


def _add_role_labels() -> None:
    """Add role labels the ORM knows but an existing ``role_enum`` does not.

    Postgres refuses to *use* a freshly added enum label in the same
    transaction, so each runs alone and commits before the constraint patch
    below quotes the new values.
    """
    for label in ("general_admin", "abona"):
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TYPE role_enum ADD VALUE IF NOT EXISTS '{label}'")
            )
    logger.info("Role enum labels are up to date")


def _patch_role_owner_constraint() -> None:
    """Rebuild ``ck_users_role_owner`` for the church amin and tenant rules."""
    statements = [
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role_owner",
        "ALTER TABLE users ADD CONSTRAINT ck_users_role_owner "
        f"CHECK ({_ROLE_OWNER_CHECK})",
    ]
    with engine.begin() as conn:
        stored = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_users_role_owner'"
            )
        ).scalar()
        if (
            stored is not None
            and "abona" in stored
            and "church_id IS NOT NULL" in stored
        ):
            return
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info("Account owner constraint now covers the church amin")


def _rebuild_legacy_general_admin_classes() -> None:
    """Drop the stage amin's class table when it still keys the login."""
    with engine.begin() as conn:
        legacy = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'general_admin_classes' AND column_name = 'user_id'"
            )
        ).scalar()
        if not legacy:
            return
        conn.execute(text("DROP TABLE IF EXISTS general_admin_classes"))
    logger.info("Stage-amin class table dropped; it is rebuilt keyed on the servant")


def create_tables() -> None:
    """Create every table the ORM declares and roll the tenant schema forward.

    Importing every feature model first guarantees it is registered on
    ``Base.metadata``, no matter which module the server was started from.
    """
    from app.features.attendance.models.attend import Attend  # noqa: F401
    from app.features.boy.models.boy import Boy  # noqa: F401
    from app.features.church.models.church import Church  # noqa: F401
    from app.features.follow_up.models.follow_up import FollowUp  # noqa: F401
    from app.features.group.models.group import Group  # noqa: F401
    from app.features.notification.models.notification_inbox import (
        NotificationInbox,  # noqa: F401
    )
    from app.features.notification.models.notification_log import (
        NotificationLog,  # noqa: F401
    )
    from app.features.notification.models.push_device import PushDevice  # noqa: F401
    from app.features.school_class.models.general_admin_class import (
        GeneralAdminClass,  # noqa: F401
    )
    from app.features.school_class.models.school_class import SchoolClass  # noqa: F401
    from app.features.subscription.models.subscription import Subscription  # noqa: F401
    from app.features.servant_trip.models.servant_trip import ServantTrip  # noqa: F401
    from app.features.servant_trip.models.servant_trip_subscription import (
        ServantTripSubscription,  # noqa: F401
    )
    from app.features.team.models.team import Team  # noqa: F401
    from app.features.team.models.team_member import TeamMember  # noqa: F401
    from app.features.team.models.team_teacher import TeamTeacher  # noqa: F401
    from app.features.task.models.task import Task  # noqa: F401
    from app.features.task_value.models.task_value import TaskValue  # noqa: F401
    from app.features.teacher.models.teacher import Teacher  # noqa: F401
    from app.features.teacher_check.models.teacher_check import TeacherCheck  # noqa: F401
    from app.features.teacher_follow_up.models.teacher_follow_up import (
        TeacherFollowUp,  # noqa: F401
    )
    from app.features.trip.models.trip import Trip  # noqa: F401
    from app.features.trip_attendance.models.trip_attendance import (
        TripAttendance,  # noqa: F401
    )
    from app.features.user.models.user import User  # noqa: F401

    _rebuild_legacy_general_admin_classes()
    Base.metadata.create_all(bind=engine)
    _add_role_labels()

    # Tenant rollout: create the anchor, add the columns, fill legacy rows,
    # then tighten the schema. Order matters - the user CHECK needs the
    # backfilled church ids before it is rebuilt.
    default_id = _ensure_default_church()
    _add_tenant_columns()
    _backfill_tenant_columns(default_id)
    _add_tenant_constraints()
    _set_tenant_columns_not_null()
    _rebuild_notification_dedupe()
    _patch_role_owner_constraint()
    _add_missing_columns()

    logger.info(
        "Database tables are ready: %s", ", ".join(sorted(Base.metadata.tables))
    )
