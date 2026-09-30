from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import ROLE_ENUM_NAME, RoleEnum

TABLE = "users"


class User(Base):
    """    Login accounts *only*: email + password + role.

    Everything else (name, phone, class) is resolved through exactly one of
    the two owner links - enforced by ``ck_users_role_owner``:

        role=teacher | role=admin -> teacher_id   (class comes from teacher)
        role=user                 -> boy_id       (class comes from boy)
        role=super_admin          -> neither      (sees every class)
    """

    __tablename__ = TABLE
    __table_args__ = (
        CheckConstraint(
            "(role IN ('teacher', 'admin') AND teacher_id IS NOT NULL AND boy_id IS NULL)"
            " OR (role = 'user' AND boy_id IS NOT NULL AND teacher_id IS NULL)"
            " OR (role = 'super_admin' AND teacher_id IS NULL AND boy_id IS NULL)",
            name="ck_users_role_owner",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum(
            RoleEnum,
            name=ROLE_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
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
    teacher = relationship("Teacher", back_populates="user", uselist=False)
    boy = relationship("Boy", back_populates="user", uselist=False)
    attends = relationship("Attend", back_populates="recorder")
    teacher_checks = relationship("TeacherCheck", back_populates="recorder")
    follow_ups = relationship("FollowUp", back_populates="recorder")

    @property
    def display_name(self) -> str | None:
        """Name comes from the linked teacher or boy - never stored here."""
        if self.teacher is not None:
            return self.teacher.teacher_name
        if self.boy is not None:
            return self.boy.boy_name
        return None

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
