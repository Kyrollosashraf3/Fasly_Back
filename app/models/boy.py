from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import GENDER_ENUM_NAME, GenderEnum

TABLE = "boys"


class Boy(Base):
    """Core boy record. ``class_id`` is his *current* class.

    ``age`` is never stored - it is derived from ``birth_date`` when needed.

    ``attends``/``follow_ups`` are history and are NOT cascade-deleted: the FK
    is RESTRICT, so a boy with recorded history cannot be dropped by accident.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
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
    location = Column(String(500), nullable=True)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
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
    class_ = relationship("SchoolClass", back_populates="boys")
    user = relationship(
        "User", back_populates="boy", uselist=False, cascade="all, delete-orphan"
    )
    attends = relationship("Attend", back_populates="boy")
    follow_ups = relationship("FollowUp", back_populates="boy")
    groups = relationship("Group", back_populates="boy", cascade="all, delete-orphan")

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
