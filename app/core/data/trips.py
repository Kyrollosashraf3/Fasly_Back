"""Trips (الرحلات) - اشتراكات الفصول في الرحلات."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import apply_update, commit, ensure_manager, get_or_404
from app.models.school_class import SchoolClass
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripUpdate


class TripService(BaseService):
    """القراءة متاحة لكل دخول مقسمة على الفصول، والكتابة للمديرين فقط."""

    def query(self) -> Query:
        return self.classes_query(Trip)

    def list(self) -> list[Trip]:
        return self.query().order_by(Trip.created_at.desc(), Trip.id.desc()).all()

    def get(self, trip_id: int) -> Trip:
        return get_or_404(self.db, Trip, trip_id, "Trip")

    def create(self, data: TripCreate) -> Trip:
        self.ensure_manager()
        self._ensure_class(data.class_id)
        trip = Trip(
            name=data.name.strip(),
            cost=data.cost,
            class_id=data.class_id,
            created_at=data.created_at or date.today(),
            recorded_by=self.user_id,
        )
        self.db.add(trip)
        commit(self.db, f"Trip create name={data.name}")
        return trip

    def update(self, trip_id: int, data: TripUpdate) -> Trip:
        trip = self.get(trip_id)
        self.ensure_manager()
        if data.class_id is not None:
            self._ensure_class(data.class_id)
        apply_update(trip, data, strip=("name",))
        commit(self.db, f"Trip update id={trip_id}")
        return trip

    def delete(self, trip_id: int) -> None:
        trip = self.get(trip_id)
        self.ensure_manager()
        self.db.delete(trip)
        commit(self.db, f"Trip delete id={trip_id}")

    def _ensure_class(self, class_id: int) -> None:
        school_class = self.db.get(SchoolClass, class_id)
        if school_class is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الفصل غير موجود.",
            )