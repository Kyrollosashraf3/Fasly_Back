from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class ServantTrip(Base):
    """Church-wide trip for servants, independent of any school class."""

    __tablename__ = "servant_trips"

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False, index=True)
    cost = Column(Integer, nullable=False, default=0)
    created_at = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    church = relationship("Church")
    recorder = relationship("User", back_populates="servant_trips")
    subscriptions = relationship(
        "ServantTripSubscription", back_populates="trip"
    )

    def __repr__(self) -> str:
        return (
            f"<ServantTrip id={self.id} name={self.name!r} "
            f"church_id={self.church_id} date={self.created_at} cost={self.cost}>"
        )
