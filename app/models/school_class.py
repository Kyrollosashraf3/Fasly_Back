from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "classes"


class SchoolClass(Base):
    """A class group for one academic year (e.g. "أولي ابتدائي", 2026/2027).

    This is the single source of truth for "الفصل". Current references live in
    ``teachers``/``boys``; a login (``users``) resolves its class through its
    ``teacher_id`` or ``boy_id``. Historical records
    (``attends``/``follow_ups``/``teacher_checks``) keep their own
    ``class_id`` snapshot so old rows never change when boys are promoted.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    church = relationship("Church")
    teachers = relationship("Teacher", back_populates="class_")
    boys = relationship("Boy", back_populates="class_")
    attends = relationship("Attend", back_populates="class_")
    follow_ups = relationship("FollowUp", back_populates="class_")
    teacher_checks = relationship("TeacherCheck", back_populates="class_")
    trips = relationship("Trip", back_populates="class_")
    tasks = relationship("Task", back_populates="class_")
    task_values = relationship("TaskValue", back_populates="class_")

    def __repr__(self) -> str:
        return (
            f"<SchoolClass id={self.id} name={self.name!r} "
            f"year={self.academic_year}>"
        )
