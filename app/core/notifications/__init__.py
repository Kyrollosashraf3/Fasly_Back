"""Web push: sending notifications to the servants' phones from this server.

    vapid.py    the key pair and whether push is switched on at all
    sender.py   the one call that talks to a push service
    service.py  what the routes ask: subscribe, target, log
    jobs.py     the clock - daily and weekly reminders

A push message leaves the app: the browser keeps the subscription with its own
push service, so a notification lands on a phone with the site closed. What the
server stores is the subscription address, nothing else.
"""

from app.core.notifications.jobs import notification_loop, run_due_jobs
from app.core.notifications.sender import deliver
from app.core.notifications.service import NotificationService, send_now
from app.core.notifications.vapid import push_enabled, vapid_public_key

__all__ = [
    "NotificationService",
    "deliver",
    "notification_loop",
    "push_enabled",
    "run_due_jobs",
    "send_now",
    "vapid_public_key",
]
