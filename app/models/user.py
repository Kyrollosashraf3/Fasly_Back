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
    """    Login accounts *only*: phone + password + role.

    The phone number is the only handle: an administrator registers the
    number (``POST /auth/register`` or the Excel import) and the owner picks
    his password himself from the signup screen. ``password_hash`` is NULL
    until then.

    Everything else (name, phone, class) is resolved through exactly one of
    the two owner links - enforced by ``ck_users_role_owner``:

        role=teacher | role=admin -> teacher_id   (class comes from teacher)
        role=user                 -> boy_id       (class comes from boy)
        role=super_admin          -> teacher_id optional, boy_id never
                                     (sees every class; teacher gives a name)
    """

    __tablename__ = TABLE
    __table_args__ = (
        CheckConstraint(
            "(role IN ('teacher', 'admin') AND teacher_id IS NOT NULL AND boy_id IS NULL)"
            " OR (role = 'user' AND boy_id IS NOT NULL AND teacher_id IS NULL)"
            " OR (role = 'super_admin' AND boy_id IS NULL)",
            name="ck_users_role_owner",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
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
    trips = relationship("Trip", back_populates="recorder")
    subscriptions = relationship("Subscription", back_populates="creator")

    @property
    def display_name(self) -> str | None:
        """Name comes from the linked teacher or boy - never stored here."""
        if self.teacher is not None:
            return self.teacher.teacher_name
        if self.boy is not None:
            return self.boy.boy_name
        return None

    @property
    def handle(self) -> str:
        """The identifier this login answers to."""
        return self.phone

    @property
    def pending_signup(self) -> bool:
        """True while the account exists but no password was set yet."""
        return not self.password_hash

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"
