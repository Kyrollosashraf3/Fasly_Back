from datetime import date

from sqlalchemy import (
    Column,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    CLASS_ENUM_NAME,
    FOLLOW_ENUM_NAME,
    ClassEnum,
    FollowEnum,
)


class FollowUp(Base):
    """Weekly follow-up call logged by a servant for one boy."""

    __tablename__ = "follow_ups"
    __table_args__ = (
        Index("ix_follow_ups_class_name_action_date", "class_name", "action_date"),
        Index("ix_follow_ups_boy_id_action_date", "boy_id", "action_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_name = Column(
        Enum(
            ClassEnum,
            name=CLASS_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
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
        default=FollowEnum.CALL,
    )
    note = Column(Text, nullable=True)
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    teacher = relationship("Teacher", back_populates="follow_ups")
    boy = relationship("Boy", back_populates="follow_ups")
    user = relationship("User", back_populates="follow_ups")

    def __repr__(self) -> str:
        return (
            f"<FollowUp id={self.id} teacher_id={self.teacher_id} "
            f"boy_id={self.boy_id} date={self.action_date} status={self.status}>"
        )
