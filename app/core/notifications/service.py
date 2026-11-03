"""The questions the notification routes ask: who subscribed, who gets it, what went.

Nothing here talks to a push service - that is ``sender.deliver``. This module
only decides *who* should receive a message and remembers that it was sent.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_logger
from app.core.data.common import MANAGERS, ensure_manager, my_class_id
from app.core.notifications.sender import MAX_FAILS, deliver
from app.core.notifications.vapid import push_enabled
from app.models.enums import RoleEnum
from app.models.notification_log import NotificationLog
from app.models.push_device import PushDevice
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.notification import SendCreate, SubscriptionCreate

logger = get_logger(__name__)

#: Anyone whose phone should ring: a servant or a class amin. The church-wide
#: amin is left out on purpose - he writes the messages, he is not notified.
RECIPIENT_ROLES = (RoleEnum.TEACHER, RoleEnum.ADMIN)

#: Where a tap lands when a message carries no link of its own.
DEFAULT_LINK = "#/"


def devices_for(db: Session, class_id: int | None) -> list[PushDevice]:
    """Live subscriptions of the servants of ``class_id`` (None = every class)."""
    query = (
        db.query(PushDevice)
        .join(User, User.id == PushDevice.user_id)
        .outerjoin(Teacher, Teacher.id == User.teacher_id)
        .filter(User.role.in_(RECIPIENT_ROLES), PushDevice.fails < MAX_FAILS)
    )
    if class_id is not None:
        query = query.filter(Teacher.class_id == class_id)
    return query.all()


def staff_count(db: Session, class_id: int | None) -> int:
    """Servants in that audience, subscribed or not.

    The send screen shows this beside the device count so an amin can see who
    has still never switched their notifications on.
    """
    query = db.query(func.count(User.id)).filter(
        User.role.in_(RECIPIENT_ROLES), User.teacher_id.isnot(None)
    )
    if class_id is not None:
        query = query.join(Teacher, Teacher.id == User.teacher_id).filter(
            Teacher.class_id == class_id
        )
    return query.scalar() or 0


def send_now(
    log_id: int,
    *,
    title: str,
    body: str,
    link: str,
    class_id: int | None,
    tag: str | None = None,
) -> None:
    """Deliver a queued message and write the counts back into its log row.

    Runs after the response, in its own session: the request session is closed
    by then, and a dozen posts to a push service must not hold it open.
    """
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        sent, failed = deliver(
            db, devices_for(db, class_id), title, body, link=link, tag=tag
        )
        log = db.get(NotificationLog, log_id)
        if log is not None:  # deleted while the send was in flight
            log.sent, log.failed = sent, failed
            db.commit()
        logger.info("notification %s: %d sent, %d failed", log_id, sent, failed)
    finally:
        db.close()


class NotificationService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.user = current_user

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
        if device is None:
            device = PushDevice(
                user_id=self.user.id,
                endpoint=data.endpoint,
                p256dh=data.keys.p256dh,
                auth=data.keys.auth,
            )
            self.db.add(device)
        else:
            device.user_id = self.user.id
            device.p256dh = data.keys.p256dh
            device.auth = data.keys.auth
            device.fails = 0
        self.db.commit()
        self.db.refresh(device)
        logger.info("push subscription saved for user=%s device=%s", self.user.id, device.id)
        return device

    # ---------------------------------------------------------------- audience

    def audience_class_id(self, requested: int | None) -> int | None:
        """The class this send may target - pinned to his own for a class amin.

        A class amin asking for ``None`` (every class) gets his class anyway:
        the body of his request cannot widen his reach.
        """
        if self.user.role == RoleEnum.SUPER_ADMIN:
            return requested

        ensure_manager(self.user)
        mine = my_class_id(self.db, self.user)
        if mine is None:
            logger.warning("amin user=%s has no class; sending to none", self.user.id)
        return mine

    def devices(self, class_id: int | None) -> list[PushDevice]:
        return devices_for(self.db, class_id)

    def count_staff(self, class_id: int | None) -> int:
        return staff_count(self.db, class_id)

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
            mine = self.audience_class_id(requested_class_id)
            out["devices"] = len(self.devices(mine))
            out["staff"] = self.count_staff(mine)
        return out

    # -------------------------------------------------------------------- send

    def queue(self, data: SendCreate) -> tuple[NotificationLog, list[PushDevice]]:
        """Write the log row and resolve the devices - before anything is sent.

        The send itself runs in the background (a dozen HTTP posts to a push
        service must not hold a request open), and it fills ``sent``/``failed``
        back into this row.
        """
        class_id = self.audience_class_id(data.class_id)
        devices = self.devices(class_id)
        log = NotificationLog(
            kind="manual",
            title=data.title.strip(),
            body=data.body.strip(),
            link=data.link or DEFAULT_LINK,
            class_id=class_id,
            audience="class" if class_id is not None else "all",
            sent=0,
            failed=0,
            sender_id=self.user.id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log, devices

    def record(self, log_id: int, sent: int, failed: int) -> None:
        log = self.db.get(NotificationLog, log_id)
        if log is None:  # the account that queued it was deleted mid-send
            return
        log.sent, log.failed = sent, failed
        self.db.commit()

    def history(self, limit: int = 50) -> list[NotificationLog]:
        query = self.db.query(NotificationLog).order_by(NotificationLog.id.desc())
        if self.user.role != RoleEnum.SUPER_ADMIN:
            mine = my_class_id(self.db, self.user)
            query = query.filter(
                (NotificationLog.class_id == mine)
                | (NotificationLog.sender_id == self.user.id)
            )
        return query.limit(limit).all()
