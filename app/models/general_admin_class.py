from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "general_admin_classes"


class GeneralAdminClass(Base):
    """Which classes a stage amin (``role=general_admin``) is responsible for.

    Keyed by ``teacher_id``, so the group belongs to the servant rather than to
    the login - he keeps it when his phone or password changes. One row per
    (servant, class), so two amins of one stage can hold different sets:
    رابعة لسادسة for one, أولى وتانية for the other.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint(
            "teacher_id", "class_id", name="uq_general_admin_classes_teacher_id_class_id"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    teacher = relationship("Teacher", back_populates="managed_classes")
    class_ = relationship("SchoolClass")

    def __repr__(self) -> str:
        return f"<GeneralAdminClass id={self.id} teacher_id={self.teacher_id} class_id={self.class_id}>"
