from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "attends"


class Attend(Base):
    """Friday attendance of one boy: ``present=True`` = حاضر, ``False`` = غائب.

    ``class_id`` is a *historical snapshot* of the boy's class on ``date``;
    promoting boys at the start of a new academic year never rewrites it.

    Every FK here is RESTRICT: this row outlives the boy, the class and the
    account that recorded it.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("boy_id", "date", name="uq_attends_boy_id_date"),
        Index("ix_attends_class_id_date", "class_id", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, default=date.today, index=True)
    present = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    boy = relationship("Boy", back_populates="attends")
    class_ = relationship("SchoolClass", back_populates="attends")
    recorder = relationship("User", back_populates="attends")

    def __repr__(self) -> str:
        return (
            f"<Attend id={self.id} boy_id={self.boy_id} "
            f"class_id={self.class_id} date={self.date} present={self.present}>"
        )
