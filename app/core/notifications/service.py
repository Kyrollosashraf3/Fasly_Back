"""The questions the notification routes ask: who subscribed, who gets it, what went.

Nothing here talks to a push service - that is ``sender.deliver``. This module
only decides *who* should receive a message, remembers that it was sent, and
keeps the copy each recipient sees in his own bell.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_logger
from app.core.data.common import (
    MANAGERS,
    ensure_manager,
    ensure_my_class,
    is_unrestricted,
    my_class_ids,
    owner_class_id,
    target_church_id,
)
from app.core.notifications.sender import MAX_FAILS, deliver
from app.core.notifications.vapid import push_enabled
from app.features.church.models.church import Church
from app.models.enums import RoleEnum
from app.features.notification.models.notification_inbox import NotificationInbox
from app.features.notification.models.notification_log import NotificationLog
from app.features.notification.models.push_device import PushDevice
from app.features.school_class.models.school_class import SchoolClass
from app.features.teacher.models.teacher import Teacher
from app.features.user.models.user import User
from app.features.notification.schemas.notification import SendCreate, SubscriptionCreate

logger = get_logger(__name__)

#: Anyone whose phone should ring: a servant, a class amin or a stage amin. The
#: church-wide amin is left out on purpose - he writes the messages, he is not
#: notified.
RECIPIENT_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN)

#: Where a tap lands when a message carries no link of its own.
DEFAULT_LINK = "#/"


def _target(query, class_id: int | None, teacher_ids: list[int] | None):
    """Apply an audience to a query already joined on ``User``.

    Named servants win over a class: ``teacher_ids`` is the narrower ask, and
    the caller has already pinned ``class_id`` to what this login may reach.
    """
    if teacher_ids is not None:
        return query.filter(User.teacher_id.in_(teacher_ids))
    if class_id is not None:
        return query.filter(Teacher.class_id == class_id)
    return query


def recipient_users(
    db: Session,
    church_id: int,
    class_id: int | None = None,
    teacher_ids: list[int] | None = None,
) -> list[User]:
    """The logins a message is written for: one church, then class / servants."""
    query = db.query(User).filter(
        User.role.in_(RECIPIENT_ROLES),
        User.teacher_id.isnot(None),
        User.church_id == church_id,
    )
    if teacher_ids is not None or class_id is not None:
        query = query.outerjoin(Teacher, Teacher.id == User.teacher_id)
    return _target(query, class_id, teacher_ids).all()


def devices_for(
    db: Session,
    church_id: int,
    class_id: int | None = None,
    teacher_ids: list[int] | None = None,
) -> list[PushDevice]:
    """Live subscriptions of that church's audience (nothing narrowed = all its classes)."""
    query = (
        db.query(PushDevice)
        .join(User, User.id == PushDevice.user_id)
        .outerjoin(Teacher, Teacher.id == User.teacher_id)
        .filter(
            User.role.in_(RECIPIENT_ROLES),
            PushDevice.fails < MAX_FAILS,
            PushDevice.church_id == church_id,
        )
    )
    return _target(query, class_id, teacher_ids).all()


def staff_count(
    db: Session,
    church_id: int,
    class_id: int | None = None,
    teacher_ids: list[int] | None = None,
) -> int:
    """Servants in that church's audience, subscribed or not.

    The send screen shows this beside the device count so an amin can see who
    has still never switched their notifications on.
    """
    query = db.query(func.count(User.id)).filter(
        User.role.in_(RECIPIENT_ROLES),
        User.teacher_id.isnot(None),
        User.church_id == church_id,
    )
    if teacher_ids is not None or class_id is not None:
        query = query.outerjoin(Teacher, Teacher.id == User.teacher_id)
    return _target(query, class_id, teacher_ids).scalar() or 0


def send_now(
    log_id: int,
    *,
    title: str,
    body: str,
    link: str,
    class_id: int | None,
    teacher_ids: list[int] | None = None,
    tag: str | None = None,
) -> None:
    """Deliver a queued message and write the counts back into its log row.

    Runs after the response, in its own session: the request session is closed
    by then, and a dozen posts to a push service must not hold it open. The
    bell rows already exist - a phone that does not answer loses a ring, not
    the message.
    """
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        log = db.get(NotificationLog, log_id)
        if log is None:  # deleted while the send was in flight
            return
        # The audience is always one church: the log was written for it, so a
        # send can never drift into another tenant even if ids are reused.
        targets = devices_for(db, log.church_id, class_id, teacher_ids)
        sent, failed = deliver(
            db,
            targets,
            title,
            body,
            link=link,
            tag=tag,
        )
        log.sent, log.failed = sent, failed
        db.commit()
        logger.info("notification %s: %d sent, %d failed", log_id, sent, failed)
    finally:
        db.close()


class NotificationService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.user = current_user

    def _send_church_id(self, class_id: int | None = None) -> int:
        """The single church a manual message belongs to.

        A tenant login is pinned to its church. The platform owner is not, so
        his send is scoped to the church of the class he picked, or to the
        configured default church for a church-wide broadcast.
        """
        return target_church_id(self.db, self.user, class_id=class_id)

    # ------------------------------------------------------------ subscriptions

    def subscribe(self, data: SubscriptionCreate) -> PushDevice:
        """Save (or refresh) this browser's subscription for the calling login.

        The endpoint is the key: a browser that rotates its subscription posts
        the same address with new keys, and a phone handed from one servant to
        another re-registers the same address under the new login.
        """
        device = (
            self.db.query(PushDevice)
            .filter(PushDevice.endpoint == data.endpoint)
            .first()
        )
        church_id = self._send_church_id()
        if device is None:
            device = PushDevice(
                user_id=self.user.id,
                church_id=church_id,
                endpoint=data.endpoint,
                p256dh=data.keys.p256dh,
                auth=data.keys.auth,
            )
            self.db.add(device)
        else:
            # A browser handed from one login to another moves with its owner,
            # tenant included - a stale church_id could leak another church's
            # message to the new owner.
            device.user_id = self.user.id
            device.church_id = church_id
            device.p256dh = data.keys.p256dh
            device.auth = data.keys.auth
            device.fails = 0
        self.db.commit()
        self.db.refresh(device)
        logger.info("push subscription saved for user=%s device=%s", self.user.id, device.id)
        return device

    # ---------------------------------------------------------------- audience

    def audience_class_id(
        self, requested: int | None, *, named_servants: bool = False
    ) -> int | None:
        """The class this send may target - the body of a request can never
        widen who receives it.

        A class amin asking for ``None`` (every class) gets his class anyway. A
        stage amin keeps his choice but must stay inside his own group: one
        message is logged against one class, so he sends class by class. He is
        only allowed to ask for all of them when he names the servants who should
        hear it - then the named list, not the class, is the audience.
        """
        if self.user.role == RoleEnum.SUPER_ADMIN:
            return requested

        ensure_manager(self.user)
        if self.user.role == RoleEnum.ABONA:
            # The church amin owns every class of his church: None means a
            # church-wide send, a picked class is checked against his church.
            if requested is not None:
                ensure_my_class(self.db, self.user, requested)
            return requested
        if self.user.role == RoleEnum.GENERAL_ADMIN:
            if requested is None:
                if not named_servants:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="اختار الفصل اللي هتبعت له - رسالة واحدة لكل فصل.",
                    )
                return None
            ensure_my_class(self.db, self.user, requested)
            return requested

        mine = owner_class_id(self.db, self.user)
        if mine is None:
            logger.warning("amin user=%s has no class; sending to none", self.user.id)
        return mine

    def audience_class_ids(self, requested: int | None) -> list[int] | None:
        """The classes a status question may cover (``None`` = church-wide).

        The counts on the send screen are read-only, so a stage amin may add up
        his whole group instead of picking one class - a send still needs the pick.
        """
        if self.user.role == RoleEnum.SUPER_ADMIN:
            return None if requested is None else [requested]

        ensure_manager(self.user)
        if self.user.role == RoleEnum.ABONA:
            if requested is not None:
                ensure_my_class(self.db, self.user, requested)
                return [requested]
            # Church-wide: every class of his own church, never another's.
            return my_class_ids(self.db, self.user) or []
        if self.user.role == RoleEnum.GENERAL_ADMIN:
            if requested is not None:
                ensure_my_class(self.db, self.user, requested)
                return [requested]
            return list(self.user.managed_class_ids)

        single = owner_class_id(self.db, self.user)
        return [] if single is None else [single]

    def audience_teacher_ids(
        self, requested: list[int] | None, class_id: int | None, church_id: int
    ) -> list[int] | None:
        """Named servants, kept inside this church and what this login may reach.

        The ids are checked against the servant rows themselves - not against
        the logins behind them - so naming a servant who has never made an
        account is a send with a smaller audience, not an error. A servant from
        another church is refused here, before any device is ever resolved.
        """
        if not requested:
            return None

        wanted = sorted({int(teacher_id) for teacher_id in requested})
        query = self.db.query(Teacher.id).filter(
            Teacher.id.in_(wanted), Teacher.church_id == church_id
        )
        if class_id is not None:
            query = query.filter(Teacher.class_id == class_id)
        allowed = {teacher_id for (teacher_id,) in query.all()}
        missing = [teacher_id for teacher_id in wanted if teacher_id not in allowed]
        if not is_unrestricted(self.user):
            # Naming servants needs its own check: a stage amin may only name
            # servants of the classes he answers for.
            reachable = my_class_ids(self.db, self.user) or []
            outside = self.db.query(Teacher.id).filter(
                Teacher.id.in_(wanted), Teacher.class_id.notin_(reachable)
            ).all()
            missing.extend(teacher_id for (teacher_id,) in outside)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="في خادم مختار مش من خدام الفصل اللي عندك صلاحية عليه.",
            )
        return wanted

    def devices(
        self,
        class_id: int | None,
        teacher_ids: list[int] | None = None,
        church_id: int | None = None,
    ) -> list[PushDevice]:
        return devices_for(
            self.db, church_id or self._send_church_id(class_id), class_id, teacher_ids
        )

    def count_staff(
        self,
        class_id: int | None,
        teacher_ids: list[int] | None = None,
        church_id: int | None = None,
    ) -> int:
        return staff_count(
            self.db, church_id or self._send_church_id(class_id), class_id, teacher_ids
        )

    def status(self, requested_class_id: int | None = None) -> dict:
        """For the enable-push banner and the send screen.

        A servant only needs the two switches; how many of his colleagues have
        a phone reachable is the amin's business, so the counts come back only
        for a manager. He may ask about one class, and a class amin asking about
        a class is still asking about his own.
        """
        subscribed = (
            self.db.query(PushDevice)
            .filter(PushDevice.user_id == self.user.id)
            .count()
        )
        out = {
            "enabled": push_enabled(),
            "subscribed": subscribed > 0,
            "devices": 0,
            "staff": 0,
        }
        if self.user.role in MANAGERS:
            targets = self.audience_class_ids(requested_class_id)
            selected = getattr(self.user, "selected_church_id", None)
            if targets is None and selected is not None:
                # The header is filtered: the owner is counting one church.
                out["devices"] = len(self.devices(None, church_id=int(selected)))
                out["staff"] = self.count_staff(None, church_id=int(selected))
            elif targets is None:
                # Platform owner asking for everything: add up church by church
                # so a single log/audience never spans two tenants.
                for (church_id,) in self.db.query(Church.id).all():
                    out["devices"] += len(self.devices(None, church_id=church_id))
                    out["staff"] += self.count_staff(None, church_id=church_id)
            else:
                out["devices"] = sum(len(self.devices(class_id)) for class_id in targets)
                out["staff"] = sum(self.count_staff(class_id) for class_id in targets)
        return out

    # -------------------------------------------------------------------- send

    def queue(
        self, data: SendCreate
    ) -> tuple[NotificationLog, list[PushDevice], list[User]]:
        """Write the log row, fill every recipient's bell, resolve the devices.

        The send itself runs in the background (a dozen HTTP posts to a push
        service must not hold a request open), and it fills ``sent``/``failed``
        back into this row. The bell rows are written here, in the request, so
        a message is readable in the app even if no phone answers.
        """
        class_id = self.audience_class_id(
            data.class_id, named_servants=bool(data.teacher_ids)
        )
        church_id = self._send_church_id(class_id)
        teacher_ids = self.audience_teacher_ids(data.teacher_ids, class_id, church_id)
        devices = self.devices(class_id, teacher_ids, church_id=church_id)
        users = recipient_users(self.db, church_id, class_id, teacher_ids)

        if teacher_ids is not None:
            audience = "servants"
        else:
            audience = "class" if class_id is not None else "all"

        log = NotificationLog(
            kind="manual",
            church_id=church_id,
            title=data.title.strip(),
            body=data.body.strip(),
            link=data.link or DEFAULT_LINK,
            class_id=class_id,
            audience=audience,
            sent=0,
            failed=0,
            sender_id=self.user.id,
        )
        self.db.add(log)
        self.db.flush()
        for user in users:
            self.db.add(
                NotificationInbox(
                    church_id=church_id,
                    user_id=user.id,
                    log_id=log.id,
                    kind=log.kind,
                    title=log.title,
                    body=log.body,
                    link=log.link,
                )
            )
        self.db.commit()
        self.db.refresh(log)
        return log, devices, users

    def record(self, log_id: int, sent: int, failed: int) -> None:
        log = self.db.get(NotificationLog, log_id)
        if log is None:  # the account that queued it was deleted mid-send
            return
        log.sent, log.failed = sent, failed
        self.db.commit()

    def history(self, limit: int = 50) -> list[NotificationLog]:
        query = self.db.query(NotificationLog).order_by(NotificationLog.id.desc())
        selected = getattr(self.user, "selected_church_id", None)
        if self.user.role != RoleEnum.SUPER_ADMIN:
            # Church first, then class: no other tenant's log is ever visible.
            query = query.filter(NotificationLog.church_id == self.user.church_id)
            mine = my_class_ids(self.db, self.user) or []
            query = query.filter(
                NotificationLog.class_id.in_(mine)
                | (NotificationLog.sender_id == self.user.id)
            )
        elif selected is not None:
            # The owner's header filter applies to the log too.
            query = query.filter(NotificationLog.church_id == int(selected))
        return query.limit(limit).all()

    # --------------------------------------------------------------------- bell

    def inbox(self, limit: int = 30, unread_only: bool = False) -> list[NotificationInbox]:
        """This login's own messages, newest first - what the header bell shows."""
        query = (
            self.db.query(NotificationInbox)
            .filter(NotificationInbox.user_id == self.user.id)
            .order_by(NotificationInbox.id.desc())
        )
        if unread_only:
            query = query.filter(NotificationInbox.read_at.is_(None))
        return query.limit(limit).all()

    def unread_count(self) -> int:
        return (
            self.db.query(func.count(NotificationInbox.id))
            .filter(
                NotificationInbox.user_id == self.user.id,
                NotificationInbox.read_at.is_(None),
            )
            .scalar()
            or 0
        )

    def mark_read(self, inbox_id: int) -> None:
        """One message opened. Someone else's row does not exist here."""
        row = (
            self.db.query(NotificationInbox)
            .filter(
                NotificationInbox.id == inbox_id,
                NotificationInbox.user_id == self.user.id,
            )
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الإشعار غير موجود.",
            )
        if row.read_at is None:
            row.read_at = datetime.now(timezone.utc)
            self.db.commit()

    def mark_all_read(self) -> int:
        """The bell's "اقرأ الكل": returns how many rows it closed."""
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(NotificationInbox)
            .filter(
                NotificationInbox.user_id == self.user.id,
                NotificationInbox.read_at.is_(None),
            )
            .update({NotificationInbox.read_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return count
