"""Handing a message to each browser's push service - and nothing else.

The server never touches a phone: it posts the encrypted payload to the
subscription address the push service gave the browser, and that service is
responsible for waking the device. So a failure here is always about a
subscription, not about a servant.
"""

import json
from datetime import datetime, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import get_logger
from app.core.notifications.vapid import claims, push_enabled, vapid_private_key
from app.models.push_device import PushDevice

logger = get_logger(__name__)

#: The push service says "this subscription is gone" with these.
DEAD_ENDPOINT_CODES = (404, 410)

#: A subscription that keeps refusing is dropped too, so one formatted-away
#: phone does not slow down every future send forever.
MAX_FAILS = 15

#: One hour: a reminder that arrives late is worse than none, and a message the
#: service held all day would land in the middle of the next one.
DEFAULT_TTL = 3600


def deliver(
    db: Session,
    devices: list[PushDevice],
    title: str,
    body: str,
    *,
    link: str | None = None,
    link_for=None,
    tag: str | None = None,
    ttl: int = DEFAULT_TTL,
) -> tuple[int, int]:
    """Send one message to many subscriptions; returns ``(sent, failed)``.

    ``link`` is the page a tap opens. ``link_for(device)`` overrides it per
    device, which is how the daily reminder points each servant at *his* class
    instead of a screen he has to filter himself.

    ``tag`` replaces an unread notification of the same tag rather than stacking
    three copies of the same reminder on the lock screen.
    """
    if not push_enabled():
        logger.warning("push is not configured (VAPID keys missing); %d skips", len(devices))
        return 0, len(devices)

    sent = failed = 0
    private_key = vapid_private_key()

    for device in devices:
        payload = {
            "title": title,
            "body": body,
            "url": link_for(device) if link_for else link,
            "tag": tag,
        }
        try:
            webpush(
                subscription_info={
                    "endpoint": device.endpoint,
                    "keys": {"p256dh": device.p256dh, "auth": device.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=private_key,
                vapid_claims=claims(),
                ttl=ttl,
            )
        except WebPushException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code in DEAD_ENDPOINT_CODES:
                logger.info("dropping dead subscription %s (%s)", device.id, code)
                db.delete(device)
            else:
                logger.warning("push failed for device %s (http %s)", device.id, code)
                _count_failure(db, device)
            failed += 1
            continue
        except Exception:  # a push service that is down must not stop the rest
            logger.exception("push crashed for device %s", device.id)
            _count_failure(db, device)
            failed += 1
            continue

        device.fails = 0
        device.last_sent_at = datetime.now(timezone.utc)
        sent += 1

    db.commit()
    return sent, failed


def _count_failure(db: Session, device: PushDevice) -> None:
    device.fails = (device.fails or 0) + 1
    if device.fails >= MAX_FAILS:
        db.delete(device)
