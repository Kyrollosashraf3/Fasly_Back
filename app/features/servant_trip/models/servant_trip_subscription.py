from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import SUBSCRIPTION_TYPE_ENUM_NAME, SubscriptionTypeEnum


class ServantTripSubscription(Base):
    """Payment or refund recorded for one servant on a church-wide trip."""

    __tablename__ = "servant_trip_subscriptions"
    __table_args__ = (
        Index(
            "ix_servant_trip_subscriptions_trip_teacher",
            "trip_id",
            "teacher_id",
        ),
        Index(
            "ix_servant_trip_subscriptions_teacher_created_at",
            "teacher_id",
            "created_at",
        ),
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
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trip_id = Column(
        Integer,
        ForeignKey("servant_trips.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type = Column(
        Enum(
            SubscriptionTypeEnum,
            name=SUBSCRIPTION_TYPE_ENUM_NAME,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    value = Column(Integer, nullable=False, default=0)
    note = Column(String, nullable=True)
    date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    church = relationship("Church")
    teacher = relationship("Teacher", back_populates="servant_trip_subscriptions")
    trip = relationship("ServantTrip", back_populates="subscriptions")
    creator = relationship("User", back_populates="servant_trip_subscriptions")

    @property
    def teacher_name(self) -> str | None:
        return self.teacher.teacher_name if self.teacher else None

    @property
    def trip_name(self) -> str | None:
        return self.trip.name if self.trip else None

    @property
    def created_by_name(self) -> str | None:
        if self.creator is None:
            return None
        return self.creator.display_name or self.creator.phone

    def __repr__(self) -> str:
        return (
            f"<ServantTripSubscription id={self.id} teacher_id={self.teacher_id} "
            f"trip_id={self.trip_id} type={self.type} value={self.value}>"
        )
