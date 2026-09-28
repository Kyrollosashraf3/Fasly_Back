from datetime import date

from sqlalchemy import (
    Column,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    ATTEND_ENUM_NAME,
    CLASS_ENUM_NAME,
    AttendEnum,
    ClassEnum,
)


class Attend(Base):
    """Friday attendance of one boy.

    """

    __tablename__ =  "attends"
    __table_args__ = (
        UniqueConstraint("boy_id", "action_date", name="uq_attends_boy_id_action_date"),
        Index("ix_attends_class_name_action_date", "class_name", "action_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(
        Enum(
            ClassEnum,
            name=CLASS_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(
        Enum(
            AttendEnum,
            name=ATTEND_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    note = Column(Text, nullable=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    boy = relationship("Boy", back_populates="attends")
    teacher = relationship("Teacher", foreign_keys=[recorded_by])

    def __repr__(self) -> str:
        return (
            f"<Attend id={self.id} boy_id={self.boy_id} "
            f"date={self.action_date} attend={self.attend}>"
        )
