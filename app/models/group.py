from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "groups"


class Group(Base):
    """Servant follow-up group membership: one row per (teacher, boy).

    No ``class_id`` here - the class is reachable through both sides
    (teacher -> class, boy -> class).
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("teacher_id", "boy_id", name="uq_groups_teacher_id_boy_id"),
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
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    church = relationship("Church")
    teacher = relationship("Teacher", back_populates="groups")
    boy = relationship("Boy", back_populates="groups")

    def __repr__(self) -> str:
        return f"<Group id={self.id} teacher_id={self.teacher_id} boy_id={self.boy_id}>"
