"""Web push: subscriptions in, messages out.

``endpoint`` and the two keys come straight from the browser's
``PushSubscription.toJSON()``; a subscription is meaningless without the
server's own VAPID pair, so keeping them is not the secret it looks like - but
they are still only ever returned to the login that registered them.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import ORMResponse


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=10, max_length=150)
    auth: str = Field(..., min_length=5, max_length=100)


class SubscriptionCreate(BaseModel):
    """The browser's own ``PushSubscription.toJSON()`` shape."""

    endpoint: str = Field(..., min_length=10, max_length=2000)
    keys: SubscriptionKeys


class SendCreate(BaseModel):
    """A hand-written message.

    ``class_id`` is who gets it: ``None`` means every servant of every class -
    which only the church-wide amin may say; a class amin is pinned to his own
    class by the service whatever the body claims. ``teacher_ids`` narrows the
    message to named servants (their ``teachers.id``) - a class amin may only
    name servants of his own class. ``link`` is the page a tap opens (a hash
    route, e.g. ``#/followup``); leave it out to open the app.
    """

    title: str = Field(..., min_length=3, max_length=120)
    body: str = Field(..., min_length=1, max_length=400)
    class_id: int | None = None
    teacher_ids: list[int] | None = Field(None, max_length=200)
    link: str | None = Field(None, max_length=200)


class SendOut(BaseModel):
    """What the send accepted: the log row plus how far it got."""

    id: int
    title: str
    body: str
    link: str | None
    audience: str
    class_id: int | None
    devices: int
    #: Logins the message landed in the inbox of - phones reachable or not.
    recipients: int


class NotificationRow(ORMResponse):
    id: int
    kind: str
    title: str
    body: str
    link: str | None
    class_id: int | None
    audience: str
    sent: int
    failed: int
    created_at: datetime


class InboxRow(ORMResponse):
    """One message in one login's own bell."""

    id: int
    kind: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class PushStatus(BaseModel):
    """For the enable-push banner and the send screen's recipient count."""

    #: False when the server has no VAPID pair - the banner then hides itself.
    enabled: bool
    #: This login already has a subscription saved.
    subscribed: bool
    #: Subscriptions of servants this login may send to.
    devices: int
    #: Servants in that same audience, subscribed or not.
    staff: int
