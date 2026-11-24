from datetime import date

from sqlalchemy import (
    Boolean,
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
from app.models.enums import (
    FATHER_ENUM_NAME,
    GENDER_ENUM_NAME,
    FatherEnum,
    GenderEnum,
)

TABLE = "boys"


class Boy(Base):
    """Core boy record. ``class_id`` is his *current* class.

    ``age`` is never stored - it is derived from ``birth_date`` when needed.

    ``last_visit_date`` mirrors :attr:`Teacher.last_visit_date`: the last
    confession/visit recorded for this boy. NULL until it happens.

    ``attends``/``follow_ups`` are history and are NOT cascade-deleted: the FK
    is RESTRICT, so a boy with recorded history cannot be dropped by accident.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    boy_name = Column(String(255), index=True, nullable=False)
    gender = Column(
        Enum(
            GenderEnum,
            name=GENDER_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    birth_date = Column(Date, nullable=True)
    phone = Column(String(50), nullable=True)
    phone_2 = Column(String(50), nullable=True)
    zone = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    father_name = Column(
        Enum(
            FatherEnum,
            name=FATHER_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    national_id = Column(String(20), nullable=True)
    skills = Column(ARRAY(String(50)), nullable=True)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    last_visit_date = Column(Date, nullable=True, index=True)
    note = Column(Text, nullable=True)
    issue_flag = Column(Boolean, nullable=False, default=False, index=True)
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
    class_ = relationship("SchoolClass", back_populates="boys")
    user = relationship(
        "User", back_populates="boy", uselist=False, cascade="all, delete-orphan"
    )
    attends = relationship("Attend", back_populates="boy")
    follow_ups = relationship("FollowUp", back_populates="boy")
    groups = relationship("Group", back_populates="boy", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="boy")
    trip_attendances = relationship("TripAttendance", back_populates="boy")
    task_values = relationship("TaskValue", back_populates="boy")
    team_memberships = relationship(
        "TeamMember", back_populates="boy", cascade="all, delete-orphan"
    )

    @property
    def teacher_id(self) -> int | None:
        """Servant who owns this boy's follow-up group.

        The link lives in ``groups``, never here: a boy belongs to exactly one
        group (``GroupsService.assign`` drops the previous row first).
        """
        return self.groups[0].teacher_id if self.groups else None

    @property
    def teacher_name(self) -> str | None:
        group = self.groups[0] if self.groups else None
        return group.teacher.teacher_name if group is not None else None

    @property
    def age(self) -> int | None:
        """Derived from ``birth_date`` - never stored in the table."""
        if self.birth_date is None:
            return None
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    def __repr__(self) -> str:
        return f"<Boy id={self.id} name={self.boy_name} class_id={self.class_id}>"
