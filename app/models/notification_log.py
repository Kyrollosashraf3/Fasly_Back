from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.database import Base

TABLE = "notification_logs"


class NotificationLog(Base):
    """Every send, hand-written or scheduled.

    ``kind`` says which: ``manual`` (an amin typed it), ``followup`` (the daily
    3pm reminder), ``birthday``, ``wednesday``. ``class_id`` is NULL for a
    church-wide message, and the link is what a tap opens - the scheduled jobs
    personalise their own link per servant and log the generic one here.

    ``dedupe_key`` is what stops a restart firing a second 3pm reminder the same
    day: the job inserts ``followup:2026-11-03`` *before* it sends, and the
    unique index makes the second attempt on that day impossible. A manual
    message leaves it NULL, and Postgres lets a unique index hold many NULLs, so
    an amin can send the same words twice on purpose.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notification_logs_dedupe_key"),
        Index("ix_notification_logs_kind_created_at", "kind", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(24), nullable=False, index=True)
    dedupe_key = Column(String(64), nullable=True)

    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String(200), nullable=True)

    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: ``all`` (church-wide) or ``class`` - kept as text because the audience of
    #: a past message must survive the class being renamed or removed.
    audience = Column(String(12), nullable=False, default="class")
    sent = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)

    sender_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog id={self.id} kind={self.kind} sent={self.sent}>"
