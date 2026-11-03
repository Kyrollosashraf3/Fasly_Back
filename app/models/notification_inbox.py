from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from app.db.database import Base

TABLE = "notification_inbox"


class NotificationInbox(Base):
    """One row per recipient, so the app's bell can answer "what is new for me?".

    ``notification_logs`` is one row per *send* - it cannot say whether a given
    login has read a message. This table is that missing half: written when the
    message goes out (by hand or by the clock) for every login in the audience,
    whether or not that login has a phone subscribed to web push.

    ``read_at`` stays NULL until the recipient opens it, and the row is dropped
    with its log when the two-week cleanup runs.
    """

    __tablename__ = TABLE
    __table_args__ = (
        Index("ix_notification_inbox_user_id_read_at", "user_id", "read_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_id = Column(
        Integer,
        ForeignKey("notification_logs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    #: ``manual`` | ``followup`` | ``birthday`` | ``wednesday`` - same wording
    #: as the log, kept here so a row reads on its own.
    kind = Column(String(24), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String(200), nullable=True)

    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NotificationInbox id={self.id} user_id={self.user_id} read={self.read_at}>"
