from datetime import datetime

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
from app.models.enums import (
    CLASS_ENUM_NAME,
    GENDER_ENUM_NAME,
    ClassEnum,
    GenderEnum,
)


class Boy(Base):

    __tablename__ = "boys"

    id = Column(Integer, primary_key=True, index=True)
    boy_name = Column(String(255), unique=True, index=True, nullable=False)
    gender = Column(
        Enum(
            GenderEnum,
            name=GENDER_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=GenderEnum.MALE,
    )
    birth_date = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    phone = Column(String(50), nullable=True)
    phone_2 = Column(String(50), nullable=True)
    zone = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    class_name = Column(
        Enum(
            ClassEnum,
            name=CLASS_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    note = Column(Text, nullable=True)
    issue_flag = Column(Boolean, nullable=False, default=False, index=True)

    # Relationships
    attends = relationship("Attend", back_populates="boy", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Boy id={self.id} name={self.boy_name} class={self.class_name}>"
