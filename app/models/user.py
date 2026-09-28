from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    CLASS_ENUM_NAME,
    ROLE_ENUM_NAME,
    ClassEnum,
    RoleEnum,
)

TABLE = "users"


class User(Base):
    """Admin / amin accounts.

    Admins see every class; an amin (RoleEnum.USER) is locked to his own
    ``class_name``.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(255), nullable=False)
    mail = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum(
            RoleEnum,
            name=ROLE_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
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
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    attends = relationship("Attend", back_populates="user")
    teacher_checks = relationship("TeacherCheck", back_populates="user")
    follow_ups = relationship("FollowUp", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} mail={self.mail} role={self.role}>"
