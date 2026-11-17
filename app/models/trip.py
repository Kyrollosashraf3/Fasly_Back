from datetime import date

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "trips"


class Trip(Base):
    """رحلة واحدة يسجل فيها فصل اشتراكات الأولاد.

    ``class_id`` يلمح الفصل الذي تتبع له الرحلة في لحظة التسجيل ولا يتغير
    عند نقل الصفوف بين الفصول لاحقًا. ``cost`` قيمة الاشتراك بالجنيه لكل
    ولد و ``created_at`` التاريخ الذي سجل فيه الخادم الرحلة.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False, index=True)
    cost = Column(Integer, nullable=False, default=0)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(String(20), nullable=False, default='active', index=True)
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    church = relationship("Church")
    class_ = relationship("SchoolClass", back_populates="trips")
    recorder = relationship("User", back_populates="trips")
    subscriptions = relationship("Subscription", back_populates="trip")

    def __repr__(self) -> str:
        return (
            f"<Trip id={self.id} name={self.name!r} "
            f"class_id={self.class_id} date={self.created_at} cost={self.cost}>"
        )