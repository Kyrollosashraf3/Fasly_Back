"""إشعارات: what a browser registers, what an amin sends, and each login's bell.

Registering is open to any staff login (a servant saves his own phone on the
browser's upsert, so a shared phone follows whoever logs in); only a manager may
send or read the log, and the service pins a class amin to his own class however
the request body is written. The bell (``/inbox``) belongs to whoever the
message was written for, so it is open to any login.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user, require_admin
from app.core.notifications import NotificationService, send_now, vapid_public_key
from app.core.notifications.vapid import push_enabled
from app.db.database import get_db
from app.models.user import User
from app.schemas.notification import (
    InboxRow,
    NotificationRow,
    PushStatus,
    SendCreate,
    SendOut,
    SubscriptionCreate,
    UnreadCount,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/vapid-key")
def vapid_key():
    """The public half of the VAPID pair, which a browser needs to subscribe.

    503 when the server has no pair configured: the app then hides the
    enable-notifications banner instead of offering something that cannot work.
    """
    if not push_enabled():
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return {"key": vapid_public_key()}


@router.put("/subscription", status_code=status.HTTP_204_NO_CONTENT)
def save_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register this browser for the calling login (idempotent)."""
    NotificationService(db, current_user).subscribe(data)


@router.get("/status", response_model=PushStatus)
def push_status(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Switches for this browser, and - for an amin - how many phones answer."""
    return NotificationService(db, current_user).status(class_id)


@router.post("/send", response_model=SendOut, status_code=status.HTTP_202_ACCEPTED)
def send_message(
    data: SendCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Queue a hand-written message; the posts to the push services follow.

    202 rather than 200 because the reply is the accepted request, not the
    delivery: ``sent``/``failed`` land in the log a few seconds later, while the
    recipients' bells already hold the message.
    """
    service = NotificationService(db, current_user)
    log, devices, users = service.queue(data)
    background.add_task(
        send_now,
        log.id,
        title=log.title,
        body=log.body,
        link=log.link,
        class_id=log.class_id,
        teacher_ids=data.teacher_ids,
        tag=f"manual-{log.id}",
    )
    return SendOut(
        id=log.id,
        title=log.title,
        body=log.body,
        link=log.link,
        audience=log.audience,
        class_id=log.class_id,
        devices=len(devices),
        recipients=len(users),
    )


@router.get("/log", response_model=list[NotificationRow])
def notification_log(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Recent sends, newest first: the amin's own and his class's scheduled ones."""
    return NotificationService(db, current_user).history(limit=min(limit, 200))


# ------------------------------------------------------------------ the bell
#
# Open to any login: whoever a message was written for reads his own rows, and
# anyone else simply has none.


@router.get("/inbox", response_model=list[InboxRow])
def notification_inbox(
    limit: int = 30,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """This login's messages, newest first."""
    return NotificationService(db, current_user).inbox(
        limit=min(limit, 100), unread_only=unread_only
    )


@router.get("/inbox/unread", response_model=UnreadCount)
def notification_unread(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The number on the header bell."""
    return {"count": NotificationService(db, current_user).unread_count()}


@router.patch("/inbox/read-all", response_model=UnreadCount)
def mark_inbox_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close every unread row this login has; replies with what it closed."""
    return {"count": NotificationService(db, current_user).mark_all_read()}


@router.patch("/inbox/{inbox_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_one_read(
    inbox_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One message opened (the bell taps it and then follows its link)."""
    NotificationService(db, current_user).mark_read(inbox_id)
