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

TABLE = "teacher_follow_ups"


class TeacherFollowUp(Base):
    """A manager's follow-up contact with one servant."""

    __tablename__ = TABLE
    __table_args__ = (
        Index("ix_teacher_follow_ups_class_id_action_date", "class_id", "action_date"),
        Index("ix_teacher_follow_ups_teacher_id_action_date", "teacher_id", "action_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
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

    church = relationship("Church")
    teacher = relationship("Teacher", back_populates="teacher_follow_ups")

    def __repr__(self) -> str:
        return (
            f"<TeacherFollowUp id={self.id} teacher_id={self.teacher_id} "
            f"class_id={self.class_id} date={self.action_date} status={self.status}>"
        )
