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
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import SUBSCRIPTION_TYPE_ENUM_NAME, SubscriptionTypeEnum

TABLE = "subscriptions"


class Subscription(Base):
    """حركة مالية لولد في رحلة: مصروف (charge) أو استرداد (recover).

    ``class_id`` يُؤخذ لحظة التسجيل من فصل الولد ولا يتغير عند النقل بين الفصول،
    حتى تبقى تقارير الرحلة صحيحة تاريخيًا.
    """

    __tablename__ = TABLE
    __table_args__ = (
        Index("ix_subscriptions_trip_id_boy_id", "trip_id", "boy_id"),
        Index("ix_subscriptions_boy_id_created_at", "boy_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trip_id = Column(
        Integer,
        ForeignKey("trips.id", ondelete="RESTRICT"),
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

    # Relationships
    church = relationship("Church")
    boy = relationship("Boy", back_populates="subscriptions")
    trip = relationship("Trip", back_populates="subscriptions")
    creator = relationship("User", back_populates="subscriptions")

    # Display helpers - the response shapes read these without extra joins.
    @property
    def boy_name(self) -> str | None:
        return self.boy.boy_name if self.boy else None

    @property
    def trip_name(self) -> str | None:
        return self.trip.name if self.trip else None

    @property
    def created_by_name(self) -> str | None:
        """Who recorded the payment: the linked servant / boy, else his phone."""
        if self.creator is None:
            return None
        return self.creator.display_name or self.creator.phone

    def __repr__(self) -> str:
        return (
            f"<Subscription id={self.id} boy_id={self.boy_id} "
            f"trip_id={self.trip_id} type={self.type} value={self.value}>"
        )
