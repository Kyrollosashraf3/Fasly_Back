from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    func,
)

from app.db.database import Base

TABLE = "churches"


class Church(Base):
    """One tenant of the platform - a church with its own classes and people.

    ``region`` is the area/region the church serves (المنطقة), ``is_active`` and
    ``expiry_date`` let the platform owner suspend or expire a subscription
    without deleting any of the church's data.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    region = Column(String(100), nullable=True, index=True)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    phone_2 = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    expiry_date = Column(Date, nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def expired(self) -> bool:
        """True when the subscription has passed its expiry date."""
        return self.expiry_date is not None and self.expiry_date < date.today()

    @property
    def usable(self) -> bool:
        """A church may log in only while active and not expired."""
        return bool(self.is_active) and not self.expired

    def __repr__(self) -> str:
        return (
            f"<Church id={self.id} name={self.name!r} "
            f"region={self.region!r} active={self.is_active}>"
        )
