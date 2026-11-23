from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.db.database import Base

TABLE = "push_devices"


class PushDevice(Base):
    """One browser push subscription belonging to one login.

    ``endpoint`` is the address the push service hands the browser; it is
    rotated now and then, so it is the natural key and the API upserts on it.
    ``p256dh`` and ``auth`` are the two secrets the payload is encrypted with:
    useless to anyone but the browser that owns them, and they are only ever
    sent back to the login that created them.

    FK is CASCADE - when an account is deleted its phones go with it, and a
    dead subscription is pruned the first time the push service answers 404/410.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(String(150), nullable=False)
    auth = Column(String(100), nullable=False)

    #: Consecutive delivery failures; a subscription that never answers is
    #: dropped rather than retried forever.
    fails = Column(Integer, nullable=False, default=0)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PushDevice id={self.id} user_id={self.user_id} fails={self.fails}>"
