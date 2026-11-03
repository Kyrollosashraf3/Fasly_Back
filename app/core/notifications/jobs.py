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
from app.models.boy import Boy
from app.models.group import Group
from app.models.notification_log import NotificationLog
from app.models.push_device import PushDevice
from app.models.teacher import Teacher
from app.models.user import User

logger = get_logger(__name__)

#: How often the loop looks at the clock. A minute is plenty: the reminders are
#: hourly events, not alarms.
TICK_SECONDS = 60

#: A reminder nobody fired at its hour is still worth sending for a while - a
#: server that was down for twenty minutes should not lose the day's nudge - but
#: after this it arrives in the middle of something else, so it is dropped.
LATE_WINDOW = timedelta(minutes=90)

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


def _audience(db: Session) -> dict[int | None, list[tuple[PushDevice, int | None]]]:
    """Live subscriptions grouped by the class of the servant behind them.

    ``None`` as the key means a login whose servant row has no class - a
    church-wide servant, who is nudged with the class-free wording.
    """
    rows = (
        db.query(PushDevice, Teacher.class_id, Teacher.id)
        .join(User, User.id == PushDevice.user_id)
        .outerjoin(Teacher, Teacher.id == User.teacher_id)
        .filter(User.role.in_(RECIPIENT_ROLES), PushDevice.fails < MAX_FAILS)
        .all()
    )
    grouped: dict[int | None, list[tuple[PushDevice, int | None]]] = {}
    for device, class_id, _teacher_id in rows:
        grouped.setdefault(class_id, []).append((device, _teacher_id))
    return grouped


def _devices(grouped: list[tuple[PushDevice, int | None]]) -> list[PushDevice]:
    return [device for device, _ in grouped]


def _with_group(db: Session, grouped: list[tuple[PushDevice, int | None]]) -> list[PushDevice]:
    """Devices of servants who have a group, i.e. boys assigned to them.

    The app has no "فقرة" table, so this is the closest honest reading: a
    servant with boys in his follow-up group has a segment to prepare; one
    without is a servant who attends and helps elsewhere.
    """
    servant_ids = [teacher_id for _, teacher_id in grouped if teacher_id is not None]
    if not servant_ids:
        return []
    has_group = {
        teacher_id
        for (teacher_id,) in db.query(Group.teacher_id)
        .filter(Group.teacher_id.in_(servant_ids))
        .distinct()
        .all()
    }
    return [device for device, teacher_id in grouped if teacher_id in has_group]


# ------------------------------------------------------------------ the lock


def _claim(
    db: Session,
    *,
    kind: str,
    day: date,
    title: str,
    body: str,
    link: str | None,
    class_id: int | None,
    part: str = "",
) -> NotificationLog | None:
    """Write today's row for this job; ``None`` means someone already fired it.

    The unique ``dedupe_key`` is the whole mechanism: inserting is the claim, so
    two workers racing over the same minute both try, and exactly one proceeds.
    """
    key = f"{kind}:{day.isoformat()}"
    if part:
        key = f"{key}:{part}"
    log = NotificationLog(
        kind=kind,
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


def _fire(db: Session, log: NotificationLog, devices: list[PushDevice]) -> None:
    """Deliver what was claimed and write the counts back into the same row."""
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
    for class_id, grouped in _audience(db).items():
        link = FOLLOW_UP_LINK.format(class_id) if class_id is not None else "#/followup"
        log = _claim(
            db,
            kind="followup",
            day=now.date(),
            title="فصلي بيفكرك",
            body="تفتقد مجموعتك - الأولاد مستنينك.",
            link=link,
            class_id=class_id,
            part=str(class_id),
        )
        if log is not None:
            _fire(db, log, _devices(grouped))


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

    found: dict[int, list[tuple[str, str]]] = {}
    rows = (
        db.query(Boy.boy_name, Boy.birth_date, Boy.class_id)
        .filter(func.extract("month", Boy.birth_date).in_({m for m, _ in wanted}))
        .all()
    )
    for name, birth, class_id in rows:
        if birth is None:
            continue
        label = wanted.get((birth.month, birth.day))
        if label is None:
            continue
        found.setdefault(class_id, []).append((label, name))

    out: dict[int, list[str]] = {}
    for class_id, hits in found.items():
        parts = []
        for mark in ("النهاردة", "بكرة"):
            names = [name for hit_mark, name in hits if hit_mark == mark]
            if names:
                parts.append(f"{mark} {'، '.join(names)}")
        out[class_id] = parts
    return out


def _birthday_reminder(db: Session, now: datetime) -> None:
    """Daily: a boy's birthday is today or tomorrow - his class's servants hear it."""
    if not _due(now, settings.BIRTHDAY_REMINDER_HOUR):
        return
    hits = _birthdays(db, now.date())
    if not hits:
        return
    audience = _audience(db)
    today = now.date()
    for class_id, parts in hits.items():
        grouped = audience.get(class_id)
        if not grouped:
            continue
        log = _claim(
            db,
            kind="birthday",
            day=today,
            title="فصلي بيفكرك - عيد ميلاد",
            body=f"عندك ولد عيد ميلاده {' • '.join(parts)}. جهزوا التهنئة.",
            link=BIRTHDAY_LINK.format(class_id),
            class_id=class_id,
            part=str(class_id),
        )
        if log is not None:
            _fire(db, log, _devices(grouped))


def _wednesday_reminder(db: Session, now: datetime) -> None:
    """Wednesday: prepare your segment - or, if none is on you, come to the lesson."""
    if now.weekday() != WEDNESDAY or not _due(now, settings.WEDNESDAY_REMINDER_HOUR):
        return
    for class_id, grouped in _audience(db).items():
        link = FOLLOW_UP_LINK.format(class_id) if class_id is not None else "#/followup"
        prepared = {device.id for device in _with_group(db, grouped)}
        segments = [
            (
                "قوم حضر فقرتك",
                "الأمين مستنيك يوم الأربعاء - جهّز فقرة مجموعتك.",
                [d for d, _ in grouped if d.id in prepared],
            ),
            (
                "حضر الدرس",
                "مش عليك فقرة يوم الأربعاء - حضورك هو المطلوب. مستنينك.",
                [d for d, _ in grouped if d.id not in prepared],
            ),
        ]
        for body_first, body, devices in segments:
            if not devices:
                continue
            log = _claim(
                db,
                kind="wednesday",
                day=now.date(),
                title=f"فصلي بيفكرك - {body_first}",
                body=body,
                link=link,
                class_id=class_id,
                part=f"{class_id}:{body_first}",
            )
            if log is not None:
                _fire(db, log, devices)


# ---------------------------------------------------------------- the loop


def run_due_jobs() -> None:
    """Fire whichever reminder is due right now; returns as soon as it tried.

    Called from the async loop through a thread, because every push post blocks
    on the network. Safe to call as often as you like: the day's claim either
    happens here or has already happened.
    """
    if not push_enabled():
        return
    now = datetime.now(_tz())
    db = SessionLocal()
    try:
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
    if not push_enabled():
        logger.warning("push is not configured; scheduled reminders stay off")
        return
    logger.info(
        "push reminders running (%s): follow-up %s:00, birthday %s:00, wednesday %s:00",
        settings.PUSH_TIMEZONE,
        settings.FOLLOW_UP_REMINDER_HOUR,
        settings.BIRTHDAY_REMINDER_HOUR,
        settings.WEDNESDAY_REMINDER_HOUR,
    )
    while True:
        await asyncio.to_thread(run_due_jobs)
        await asyncio.sleep(TICK_SECONDS)
