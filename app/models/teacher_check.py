from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    ATTEND_ENUM_NAME,
    CLASS_ENUM_NAME,
    AttendEnum,
    ClassEnum,
)

TABLE = "teacher_checks"


class TeacherCheck(Base):
    """Weekly check on one servant.

    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint(
            "teacher_id", "action_date", name="uq_teacher_checks_teacher_id_action_date"
        ),
        Index("ix_teacher_checks_class_name_action_date", "class_name", "action_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
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
    date = Column(Date, nullable=False, default=date.today, index=True)
    
    attend =  Column(Boolean, nullable=False, default=False)
    prepare = Column(Boolean, nullable=False, default=False)
    liturgy = Column(Boolean, nullable=False, default=False)
    follow = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Relationships
    teacher = relationship("Teacher", back_populates="teacher_checks")
    user = relationship("User", back_populates="teacher_checks")

    def __repr__(self) -> str:
        return (
            f"<TeacherCheck id={self.id} teacher_id={self.teacher_id} "
            f"date={self.action_date} attend={self.attend}>"
        )
