from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "teacher_checks"


class TeacherCheck(Base):
    """Weekly check the amin runs over the servants of his class.

    ``class_id`` is a *historical snapshot* of the servant's class on ``date``.

    Every FK here is RESTRICT: this row outlives the servant, the class and
    the account that recorded it.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("teacher_id", "date", name="uq_teacher_checks_teacher_id_date"),
        Index("ix_teacher_checks_class_id_date", "class_id", "date"),
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
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, default=date.today, index=True)

    attend = Column(Boolean, nullable=False, default=False)
    prepare = Column(Boolean, nullable=False, default=False)
    liturgy = Column(Boolean, nullable=False, default=False)
    follow = Column(Boolean, nullable=False, default=False)
    teachers_meeting = Column(Boolean, nullable=False, default=False)
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
    church = relationship("Church")
    teacher = relationship("Teacher", back_populates="teacher_checks")
    class_ = relationship("SchoolClass", back_populates="teacher_checks")
    recorder = relationship("User", back_populates="teacher_checks")

    def __repr__(self) -> str:
        return (
            f"<TeacherCheck id={self.id} teacher_id={self.teacher_id} "
            f"class_id={self.class_id} date={self.date} attend={self.attend}>"
        )
