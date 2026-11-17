from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import FATHER_ENUM_NAME, FatherEnum

TABLE = "teachers"


class Teacher(Base):
    """Servant (أساتذة/خدام) master data.

    Not a login account: the account lives in ``users`` and points back here
    via ``users.teacher_id``. ``duty`` was dropped - what he can see is
    driven entirely by ``users.role``.

``last_visit_date`` is the last time the father (أبونا) came for
    confession/visit. It starts NULL and is filled in as visits happen.

    ``class_id`` is NULL for a church-wide (super) admin: those servants do
    not belong to one class, their scope is every class.

    ``follow_ups``/``teacher_checks`` are history and are NOT cascade-deleted:
    the FK is RESTRICT, so a servant with recorded history cannot be dropped
    by accident.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_name = Column(String(255), nullable=False, index=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String(50), nullable=True)
    phone_2 = Column(String(50), nullable=True)
    zone = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    father_name = Column(
        Enum(
            FatherEnum,
            name=FATHER_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    skills = Column(ARRAY(String(50)), nullable=True)
    last_visit_date = Column(Date, nullable=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    church = relationship("Church")
    class_ = relationship("SchoolClass", back_populates="teachers")
    user = relationship(
        "User", back_populates="teacher", uselist=False, cascade="all, delete-orphan"
    )
    groups = relationship("Group", back_populates="teacher", cascade="all, delete-orphan")
    follow_ups = relationship("FollowUp", back_populates="teacher")
    teacher_checks = relationship("TeacherCheck", back_populates="teacher")
    task_values = relationship("TaskValue", back_populates="teacher")
    managed_classes = relationship(
        "GeneralAdminClass", back_populates="teacher", cascade="all, delete-orphan"
    )

    @property
    def age(self) -> int | None:
        """Derived from ``birth_date`` - never stored in the table."""
        if self.birth_date is None:
            return None
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    def __repr__(self) -> str:
        return f"<Teacher id={self.id} name={self.teacher_name} class_id={self.class_id}>"
