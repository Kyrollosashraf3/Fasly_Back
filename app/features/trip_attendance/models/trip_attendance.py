"""Trip attendance sheet - one row per (trip, boy) on the trip day.

The row answers two questions at once:

* ``attend_flag`` - did the boy show up on the trip?
* ``teacher_id``  - which servant is responsible for him on that trip?

There is deliberately no ``class_id`` here: the class is the trip's class
(``trip.class_id``), a historical snapshot that never moves. ``church_id``
keeps every row inside its tenant, exactly like the rest of the schema.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "trip_attendances"


class TripAttendance(Base):
    """حضور ولد في رحلة وتوزيعه على خادم واحد داخل الرحلة.

    صف واحد لكل (رحلة، ولد): ``attend_flag`` بيقول حضر ولا لا، و``teacher_id``
    بيقول مين الخادم المسئول عنه في الرحلة دي. الفصل مش مخزن هنا لأنه متاح من
    الرحلة نفسها (``trip.class_id``) كصورة تاريخية ثابتة.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint(
            "trip_id", "boy_id", name="uq_trip_attendances_trip_id_boy_id"
        ),
        Index("ix_trip_attendances_trip_id_teacher_id", "trip_id", "teacher_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trip_id = Column(
        Integer,
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attend_flag = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    church = relationship("Church")
    trip = relationship("Trip", back_populates="trip_attendances")
    teacher = relationship("Teacher", back_populates="trip_attendances")
    boy = relationship("Boy", back_populates="trip_attendances")

    # Display helpers - the response shapes read these without extra joins.
    @property
    def boy_name(self) -> str | None:
        return self.boy.boy_name if self.boy else None

    @property
    def teacher_name(self) -> str | None:
        return self.teacher.teacher_name if self.teacher else None

    @property
    def trip_name(self) -> str | None:
        return self.trip.name if self.trip else None

    def __repr__(self) -> str:
        return (
            f"<TripAttendance id={self.id} trip_id={self.trip_id} "
            f"boy_id={self.boy_id} teacher_id={self.teacher_id} "
            f"attend_flag={self.attend_flag}>"
        )
