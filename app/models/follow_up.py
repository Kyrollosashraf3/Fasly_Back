from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import FOLLOW_ENUM_NAME, FollowEnum

TABLE = "follow_ups"


class FollowUp(Base):
    """Weekly follow-up contact logged by a servant for one boy.

    ``class_id`` is a *historical snapshot* taken on ``action_date`` - it is
    never updated when boys are promoted.

    Every FK here is RESTRICT: this row outlives the boy, the servant, the
    class and the account that recorded it.
    """

    __tablename__ = TABLE
    __table_args__ = (
        Index("ix_follow_ups_class_id_action_date", "class_id", "action_date"),
        Index("ix_follow_ups_boy_id_action_date", "boy_id", "action_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_date = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(
        Enum(
            FollowEnum,
            name=FOLLOW_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    note = Column(Text, nullable=True)
    recorded_by = Column(
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

    # Relationships
    teacher = relationship("Teacher", back_populates="follow_ups")
    boy = relationship("Boy", back_populates="follow_ups")
    class_ = relationship("SchoolClass", back_populates="follow_ups")
    recorder = relationship("User", back_populates="follow_ups")

    def __repr__(self) -> str:
        return (
            f"<FollowUp id={self.id} teacher_id={self.teacher_id} "
            f"boy_id={self.boy_id} class_id={self.class_id} "
            f"date={self.action_date} status={self.status}>"
        )
