"""The clock: the reminders that go out on their own, with nobody asking.

Three jobs, each firing at most once a day:

    follow-up   every day at 3pm  - a servant's class nudging him to visit his group
    birthday    every morning     - a boy's birthday is today or tomorrow
    wednesday   every wednesday   - prepare your segment, or come to the lesson

A tap opens the app on the exact page, already filtered to that servant's class -
so the link is built per class, never as a generic home-page pointer.

The ``notification_logs.dedupe_key`` column is what makes a job fire once. The
row is written *before* anything is sent, so a restart, a second worker or a
loop that ticks twice a minute cannot put the same reminder on a phone twice.

A fourth job, ``_purge``, runs every tick and needs no claim: it drops messages
older than ``KEEP_DAYS`` so a bell never fills up with last month's reminders. It
runs whether or not web push is configured, which is why the loop itself does
too - cleaning up does not need a VAPID pair.
"""

from __future__ import annotations

import asyncio
import calendar
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.core.notifications.sender import MAX_FAILS, deliver
from app.core.notifications.service import RECIPIENT_ROLES
from app.core.notifications.vapid import push_enabled
from app.db.database import SessionLocal
from app.features.boy.models.boy import Boy
from app.features.group.models.group import Group
from app.features.notification.models.notification_inbox import NotificationInbox
from app.features.notification.models.notification_log import NotificationLog
from app.features.notification.models.push_device import PushDevice
from app.features.teacher.models.teacher import Teacher
from app.features.user.models.user import User

logger = get_logger(__name__)

#: How often the loop looks at the clock. A minute is plenty: the reminders are
#: hourly events, not alarms.
TICK_SECONDS = 60

#: A reminder nobody fired at its hour is still worth sending for a while - a
#: server that was down for twenty minutes should not lose the day's nudge - but
#: after this it arrives in the middle of something else, so it is dropped.
LATE_WINDOW = timedelta(minutes=90)

#: How long a message stays readable - in the bell and in the amin's log - before
#: the clock throws it away. Two weeks.
KEEP_DAYS = 14

WEDNESDAY = 2  # date.weekday(): Monday is 0.

#: The pages a tap opens. ``class_id`` is filled in per audience. A birthday
#: needs no window in the link: the page's own default (two weeks) holds today.
FOLLOW_UP_LINK = "#/followup?class_id={}"
BIRTHDAY_LINK = "#/birthdays?class_id={}"


@lru_cache(maxsize=1)
def _tz() -> ZoneInfo:
    """The church's timezone - the hours below are meant in it, not in UTC."""
    return ZoneInfo(settings.PUSH_TIMEZONE)


# ------------------------------------------------------------------ audience


def _audience(
    db: Session,
) -> dict[tuple[int, int | None], list[tuple[PushDevice, int | None]]]:
    """Live subscriptions grouped by (church, class) of the servant behind them.

    A log and its dedupe key belong to one church, so grouping by class alone
    is not enough: two tenants may each have a class that needs the same
    reminder. ``None`` as the class key is a servant with no class - the amin,
    nudged with the class-free wording.
    """
    rows = (
        db.query(PushDevice, PushDevice.church_id, Teacher.class_id, Teacher.id)
        .join(User, User.id == PushDevice.user_id)
        .outerjoin(Teacher, Teacher.id == User.teacher_id)
        .filter(User.role.in_(RECIPIENT_ROLES), PushDevice.fails < MAX_FAILS)
        .all()
    )
    grouped: dict[tuple[int, int | None], list[tuple[PushDevice, int | None]]] = {}
    for device, church_id, class_id, _teacher_id in rows:
        grouped.setdefault((church_id, class_id), []).append((device, _teacher_id))
    return grouped


def _devices(grouped: list[tuple[PushDevice, int | None]]) -> list[PushDevice]:
    return [device for device, _ in grouped]


def _audience_users(db: Session) -> dict[tuple[int, int | None], list[User]]:
    """Recipient logins grouped by (church, class), devices or none.

    The bell must hold a reminder even for a servant who never switched web
    push on, so this asks for logins rather than subscriptions. Same keys as
    ``_audience``: ``(church_id, None)`` is a servant with no class.
    """
    rows = (
        db.query(User, Teacher.class_id)
        .join(Teacher, Teacher.id == User.teacher_id)
        .filter(User.role.in_(RECIPIENT_ROLES), User.teacher_id.isnot(None))
        .all()
    )
    grouped: dict[tuple[int, int | None], list[User]] = {}
    for user, class_id in rows:
        grouped.setdefault((user.church_id, class_id), []).append(user)
    return grouped


def _servants_with_group(db: Session, servant_ids: list[int]) -> set[int]:
    """Which of these servants have a group, i.e. boys assigned to them."""
    if not servant_ids:
        return set()
    return {
        teacher_id
        for (teacher_id,) in db.query(Group.teacher_id)
        .filter(Group.teacher_id.in_(servant_ids))
        .distinct()
        .all()
    }


def _with_group(db: Session, grouped: list[tuple[PushDevice, int | None]]) -> list[PushDevice]:
    """Devices of servants who have a group, i.e. boys assigned to them.

    The app has no "فقرة" table, so this is the closest honest reading: a
    servant with boys in his follow-up group has a segment to prepare; one
    without is a servant who attends and helps elsewhere.
    """
    has_group = _servants_with_group(
        db, [teacher_id for _, teacher_id in grouped if teacher_id is not None]
    )
    return [device for device, teacher_id in grouped if teacher_id in has_group]


# ------------------------------------------------------------------ the lock


def _claim(
    db: Session,
    *,
    church_id: int,
    kind: str,
    day: date,
    title: str,
    body: str,
    link: str | None,
    class_id: int | None,
    part: str = "",
) -> NotificationLog | None:
    """Write today's row for this job; ``None`` means someone already fired it.

    The unique ``(church_id, dedupe_key)`` is the whole mechanism: inserting is
    the claim, so two workers racing over the same minute both try, and exactly
    one proceeds - while two churches each still fire their own reminder.
    """
    key = f"{church_id}:{kind}:{day.isoformat()}"
    if part:
        key = f"{key}:{part}"
    log = NotificationLog(
        kind=kind,
        church_id=church_id,
        dedupe_key=key,
        title=title,
        body=body,
        link=link,
        class_id=class_id,
        audience="class" if class_id is not None else "all",
        sent=0,
        failed=0,
    )
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return log


def _fire(
    db: Session,
    log: NotificationLog,
    devices: list[PushDevice],
    users: list[User] | None = None,
) -> None:
    """Put the message in each bell, deliver it to the phones, record the counts.

    The bell rows come first and do not depend on a phone answering: a servant
    who never switched push on still finds the reminder in the app.
    """
    for user in users or []:
        db.add(
            NotificationInbox(
                church_id=log.church_id,
                user_id=user.id,
                log_id=log.id,
                kind=log.kind,
                title=log.title,
                body=log.body,
                link=log.link,
            )
        )
    if not devices:
        log.sent, log.failed = 0, 0
        db.commit()
        return
    sent, failed = deliver(
        db, devices, log.title, log.body, link=log.link, tag=f"{log.kind}-{log.dedupe_key}"
    )
    log.sent, log.failed = sent, failed
    db.commit()
    logger.info("%s -> %d sent, %d failed", log.dedupe_key, sent, failed)


# ----------------------------------------------------------------- the jobs


def _due(now: datetime, hour: int) -> bool:
    """Is ``hour`` today, and are we still inside the late window for it?"""
    if now.hour < hour:
        return False
    return now - now.replace(hour=hour, minute=0, second=0) < LATE_WINDOW


def _follow_up_reminder(db: Session, now: datetime) -> None:
    """Daily: «فصلي بيفكرك تفتقد مجموعتك» - each class, at its own 3pm."""
    if not _due(now, settings.FOLLOW_UP_REMINDER_HOUR):
        return
    users_by_class = _audience_users(db)
    for (church_id, class_id), grouped in _audience(db).items():
        link = FOLLOW_UP_LINK.format(class_id) if class_id is not None else "#/followup"
        log = _claim(
            db,
            church_id=church_id,
            kind="followup",
            day=now.date(),
            title="فصلي بيفكرك",
            body="تفتقد مجموعتك - الأولاد مستنينك.",
            link=link,
            class_id=class_id,
            part=str(class_id),
        )
        if log is not None:
            _fire(
                db, log, _devices(grouped),
                users_by_class.get((church_id, class_id), []),
            )


def _birthdays(db: Session, today: date) -> dict[int, list[str]]:
    """Boys whose birthday is today or tomorrow, by class, name first.

    ``birth_date`` is a real date and the match is on month and day, so the
    lookup is done in Python over the few hundred boys of one church - the only
    rule worth writing out is the leap day: a 29 February birthday is celebrated
    with 28 February in a year that has no 29th.
    """
    marks = {today: "النهاردة", today + timedelta(days=1): "بكرة"}
    wanted = {(d.month, d.day): label for d, label in marks.items()}
    if (2, 29) not in wanted and (2, 28) in wanted and not calendar.isleap(today.year):
        wanted[(2, 29)] = wanted[(2, 28)]

    found: dict[tuple[int, int], list[tuple[str, str]]] = {}
    rows = (
        db.query(Boy.church_id, Boy.boy_name, Boy.birth_date, Boy.class_id)
        .filter(func.extract("month", Boy.birth_date).in_({m for m, _ in wanted}))
        .all()
    )
    for church_id, name, birth, class_id in rows:
        if birth is None:
            continue
        label = wanted.get((birth.month, birth.day))
        if label is None:
            continue
        found.setdefault((church_id, class_id), []).append((label, name))

    out: dict[tuple[int, int], list[str]] = {}
    for (church_id, class_id), hits in found.items():
        parts = []
        for mark in ("النهاردة", "بكرة"):
            names = [name for hit_mark, name in hits if hit_mark == mark]
            if names:
                parts.append(f"{mark} {'، '.join(names)}")
        out[(church_id, class_id)] = parts
    return out


def _birthday_reminder(db: Session, now: datetime) -> None:
    """Daily: a boy's birthday is today or tomorrow - his class's servants hear it."""
    if not _due(now, settings.BIRTHDAY_REMINDER_HOUR):
        return
    hits = _birthdays(db, now.date())
    if not hits:
        return
    audience = _audience(db)
    users_by_class = _audience_users(db)
    today = now.date()
    for (church_id, class_id), parts in hits.items():
        grouped = audience.get((church_id, class_id))
        if not grouped:
            continue
        log = _claim(
            db,
            church_id=church_id,
            kind="birthday",
            day=today,
            title="فصلي بيفكرك - عيد ميلاد",
            body=f"عندك ولد عيد ميلاده {' • '.join(parts)}. جهزوا التهنئة.",
            link=BIRTHDAY_LINK.format(class_id),
            class_id=class_id,
            part=str(class_id),
        )
        if log is not None:
            _fire(
                db, log, _devices(grouped),
                users_by_class.get((church_id, class_id), []),
            )


def _wednesday_reminder(db: Session, now: datetime) -> None:
    """Wednesday: prepare your segment - or, if none is on you, come to the lesson."""
    if now.weekday() != WEDNESDAY or not _due(now, settings.WEDNESDAY_REMINDER_HOUR):
        return
    users_by_class = _audience_users(db)
    for (church_id, class_id), grouped in _audience(db).items():
        link = FOLLOW_UP_LINK.format(class_id) if class_id is not None else "#/followup"
        prepared = {device.id for device in _with_group(db, grouped)}
        class_users = users_by_class.get((church_id, class_id), [])
        on_segment = _servants_with_group(db, [u.teacher_id for u in class_users])
        segments = [
            (
                "قوم حضر فقرتك",
                "الأمين مستنيك يوم الأربعاء - جهّز فقرة مجموعتك.",
                [d for d, _ in grouped if d.id in prepared],
                [u for u in class_users if u.teacher_id in on_segment],
            ),
            (
                "حضر الدرس",
                "مش عليك فقرة يوم الأربعاء - حضورك هو المطلوب. مستنينك.",
                [d for d, _ in grouped if d.id not in prepared],
                [u for u in class_users if u.teacher_id not in on_segment],
            ),
        ]
        for body_first, body, devices, users in segments:
            if not devices and not users:
                continue
            log = _claim(
                db,
                church_id=church_id,
                kind="wednesday",
                day=now.date(),
                title=f"فصلي بيفكرك - {body_first}",
                body=body,
                link=link,
                class_id=class_id,
                part=f"{class_id}:{body_first}",
            )
            if log is not None:
                _fire(db, log, devices, users)


# ---------------------------------------------------------------- the loop


def _purge(db: Session, now: datetime) -> None:
    """Throw away messages older than ``KEEP_DAYS`` - two weeks, then gone.

    Both halves go: the bell rows so a servant's list never grows, and the
    amin's log so the send history stays the last fortnight's. Deleting by
    ``created_at`` is its own idempotency, so this needs no claim row and can
    run on every tick.
    """
    cutoff = now - timedelta(days=KEEP_DAYS)
    inbox = (
        db.query(NotificationInbox)
        .filter(NotificationInbox.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    logs = (
        db.query(NotificationLog)
        .filter(NotificationLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    if inbox or logs:
        db.commit()
        logger.info("notifications older than %d days cleared: %d bell, %d log", KEEP_DAYS, inbox, logs)


def run_due_jobs() -> None:
    """Clean up, then fire whichever reminder is due; returns as soon as it tried.

    Called from the async loop through a thread, because every push post blocks
    on the network. Safe to call as often as you like: the day's claim either
    happens here or has already happened, and the purge only ever deletes rows
    that are already too old.
    """
    now = datetime.now(_tz())
    db = SessionLocal()
    try:
        _purge(db, now)
        if push_enabled():
            _follow_up_reminder(db, now)
            _birthday_reminder(db, now)
            _wednesday_reminder(db, now)
    except Exception:
        db.rollback()
        logger.exception("scheduled notifications failed")
    finally:
        db.close()


async def notification_loop() -> None:
    """The lifespan's only background task: look at the clock, once a minute."""
    if push_enabled():
        logger.info(
            "push reminders running (%s): follow-up %s:00, birthday %s:00, wednesday %s:00",
            settings.PUSH_TIMEZONE,
            settings.FOLLOW_UP_REMINDER_HOUR,
            settings.BIRTHDAY_REMINDER_HOUR,
            settings.WEDNESDAY_REMINDER_HOUR,
        )
    else:
        logger.warning(
            "push is not configured; reminders stay off but old messages still clear"
        )
    while True:
        await asyncio.to_thread(run_due_jobs)
        await asyncio.sleep(TICK_SECONDS)
