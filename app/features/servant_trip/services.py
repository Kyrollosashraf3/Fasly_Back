"""Church-wide servant trips and their payment ledger."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, joinedload

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_my_church,
    ensure_roles,
    get_or_404,
    scope_church,
    MANAGERS,
)
from app.features.servant_trip.models.servant_trip import ServantTrip
from app.features.servant_trip.models.servant_trip_subscription import (
    ServantTripSubscription,
)
from app.features.servant_trip.schemas.servant_trip import (
    ServantTripCreate,
    ServantTripUpdate,
)
from app.features.servant_trip.schemas.servant_trip_subscription import (
    ServantTripSubscriptionCreate,
    ServantTripSubscriptionUpdate,
    ServantTripSummary,
    ServantTripTotal,
)
from app.features.teacher.models.teacher import Teacher
from app.features.user.models.user import User
from app.models.enums import SubscriptionTypeEnum


class ServantTripService(BaseService):
    """Manage trips visible to all managers in a church, not one class."""

    def _require_manager(self) -> None:
        ensure_roles(self.user, *MANAGERS)

    def query(self) -> Query:
        return scope_church(
            self.db.query(ServantTrip), ServantTrip, self.user
        )

    def list(self, status_filter: str | None = "active") -> list[ServantTrip]:
        self._require_manager()
        query = self.query()
        if status_filter in ("active", "inactive"):
            query = query.filter(ServantTrip.status == status_filter)
        return query.order_by(
            ServantTrip.created_at.desc(), ServantTrip.id.desc()
        ).all()

    def get(self, trip_id: int) -> ServantTrip:
        self._require_manager()
        trip = self.query().filter(ServantTrip.id == trip_id).first()
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="رحلة الخدام غير موجودة.",
            )
        return trip

    def create(self, data: ServantTripCreate) -> ServantTrip:
        self._require_manager()
        church_id = self.church_for()
        created_at = data.created_at or date.today()
        self._ensure_no_duplicate(data.name, created_at, church_id)
        trip = ServantTrip(
            church_id=church_id,
            name=data.name,
            cost=data.cost,
            created_at=created_at,
            status=data.status or "active",
            recorded_by=self.user_id,
        )
        self.db.add(trip)
        commit(self.db, f"Servant trip create name={data.name}")
        return trip

    def update(self, trip_id: int, data: ServantTripUpdate) -> ServantTrip:
        trip = self.get(trip_id)
        new_name = (data.name or "").strip() or trip.name
        new_date = data.created_at if data.created_at is not None else trip.created_at
        if (new_name, new_date) != (trip.name, trip.created_at):
            self._ensure_no_duplicate(
                new_name, new_date, trip.church_id, exclude_id=trip.id
            )
        apply_update(trip, data, strip=("name",))
        commit(self.db, f"Servant trip update id={trip_id}")
        return trip

    def delete(self, trip_id: int) -> None:
        trip = self.get(trip_id)
        self.db.delete(trip)
        commit(self.db, f"Servant trip delete id={trip_id}")

    def _ensure_no_duplicate(
        self,
        name: str,
        created_at: date,
        church_id: int,
        exclude_id: int | None = None,
    ) -> None:
        query = self.db.query(ServantTrip).filter(
            ServantTrip.church_id == church_id,
            ServantTrip.name == name,
            ServantTrip.created_at == created_at,
        )
        if exclude_id is not None:
            query = query.filter(ServantTrip.id != exclude_id)
        if query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رحلة للخدام بهذا الاسم والتاريخ موجودة بالفعل.",
            )


class ServantTripSubscriptionService(BaseService):
    """Manage church-wide servant payment records and summaries."""

    def _require_manager(self) -> None:
        ensure_roles(self.user, *MANAGERS)

    def query(self) -> Query:
        return scope_church(
            self.db.query(ServantTripSubscription),
            ServantTripSubscription,
            self.user,
        )

    @staticmethod
    def _with_names(query: Query) -> Query:
        return query.options(
            joinedload(ServantTripSubscription.teacher),
            joinedload(ServantTripSubscription.trip),
            joinedload(ServantTripSubscription.creator).joinedload(User.teacher),
        )

    def list(self) -> list[ServantTripSubscription]:
        self._require_manager()
        return (
            self._with_names(self.query())
            .order_by(
                ServantTripSubscription.created_at.desc(),
                ServantTripSubscription.id.desc(),
            )
            .all()
        )

    def get(self, subscription_id: int) -> ServantTripSubscription:
        self._require_manager()
        subscription = (
            self._with_names(self.query())
            .filter(ServantTripSubscription.id == subscription_id)
            .first()
        )
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="اشتراك الخادم في الرحلة غير موجود.",
            )
        return subscription

    def get_for_trip(self, trip_id: int) -> list[ServantTripSubscription]:
        self._trip(trip_id)
        return (
            self._with_names(self.query())
            .filter(ServantTripSubscription.trip_id == trip_id)
            .order_by(
                ServantTripSubscription.created_at.desc(),
                ServantTripSubscription.id.desc(),
            )
            .all()
        )

    def create(
        self, data: ServantTripSubscriptionCreate
    ) -> ServantTripSubscription:
        self._require_manager()
        trip = self._trip(data.trip_id)
        teacher = get_or_404(self.db, Teacher, data.teacher_id, "Servant")
        ensure_my_church(self.db, self.user, teacher.church_id)
        if teacher.church_id != trip.church_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الخادم والرحلة يجب أن يكونا في نفس الكنيسة.",
            )

        created_at = data.created_at or datetime.utcnow()
        duplicate = (
            self.db.query(ServantTripSubscription)
            .filter(
                ServantTripSubscription.teacher_id == teacher.id,
                ServantTripSubscription.trip_id == trip.id,
                ServantTripSubscription.value == data.value,
                ServantTripSubscription.created_at
                >= created_at - timedelta(minutes=2),
                ServantTripSubscription.created_at
                <= created_at + timedelta(minutes=2),
            )
            .first()
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="تم تسجيل هذا المبلغ للخادم في الرحلة خلال الدقيقتين الماضيتين.",
            )

        summary = self._summary_for(trip, teacher)
        if data.type == SubscriptionTypeEnum.CHARGE:
            if data.value > summary.remaining:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"المبلغ أكبر من الباقي عليه ({summary.remaining} جنيه).",
                )
        elif data.value > summary.total_charged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "لا يمكن استرداد أكثر مما دفعه الخادم مسبقاً "
                    f"({summary.total_charged} جنيه)."
                ),
            )

        subscription = ServantTripSubscription(
            church_id=trip.church_id,
            teacher_id=teacher.id,
            trip_id=trip.id,
            type=SubscriptionTypeEnum(data.type),
            value=data.value,
            note=data.note,
            date=data.date or date.today(),
            created_at=created_at,
            created_by=self.user_id,
        )
        self.db.add(subscription)
        commit(
            self.db,
            f"Servant trip subscription create teacher={teacher.id} trip={trip.id}",
        )
        return self.get(subscription.id)

    def update(
        self, subscription_id: int, data: ServantTripSubscriptionUpdate
    ) -> ServantTripSubscription:
        subscription = self.get(subscription_id)
        apply_update(subscription, data)
        if data.type is not None:
            subscription.type = SubscriptionTypeEnum(data.type)
        commit(self.db, f"Servant trip subscription update id={subscription_id}")
        return subscription

    def delete(self, subscription_id: int) -> None:
        subscription = self.get(subscription_id)
        self.db.delete(subscription)
        commit(self.db, f"Servant trip subscription delete id={subscription_id}")

    def get_totals(self, trip_id: int) -> list[ServantTripTotal]:
        trip = self._trip(trip_id)
        summaries = self._trip_summaries(trip)
        return [
            ServantTripTotal(
                teacher_id=item.teacher_id,
                teacher_name=item.teacher_name,
                total_paid=item.total_paid,
            )
            for item in summaries
            if item.total_paid > 0
        ]

    def get_trip_summary(self, trip_id: int) -> list[ServantTripSummary]:
        return self._trip_summaries(self._trip(trip_id))

    def get_servant_summary(
        self, trip_id: int, teacher_id: int
    ) -> ServantTripSummary:
        trip = self._trip(trip_id)
        teacher = get_or_404(self.db, Teacher, teacher_id, "Servant")
        ensure_my_church(self.db, self.user, teacher.church_id)
        if teacher.church_id != trip.church_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الخادم غير موجود في نطاق الرحلة.",
            )
        return self._summary_for(trip, teacher)

    def _trip(self, trip_id: int) -> ServantTrip:
        return ServantTripService(self.db, self.user).get(trip_id)

    def _trip_summaries(self, trip: ServantTrip) -> list[ServantTripSummary]:
        teachers = (
            self.db.query(Teacher)
            .filter(Teacher.church_id == trip.church_id)
            .order_by(Teacher.teacher_name)
            .all()
        )
        subscriptions = (
            self.db.query(ServantTripSubscription)
            .filter(ServantTripSubscription.trip_id == trip.id)
            .all()
        )
        by_teacher: dict[int, list[ServantTripSubscription]] = {}
        for subscription in subscriptions:
            by_teacher.setdefault(subscription.teacher_id, []).append(subscription)
        return [
            self._summary_for(trip, teacher, by_teacher.get(teacher.id, []))
            for teacher in teachers
        ]

    def _summary_for(
        self,
        trip: ServantTrip,
        teacher: Teacher,
        subscriptions: list[ServantTripSubscription] | None = None,
    ) -> ServantTripSummary:
        if subscriptions is None:
            subscriptions = (
                self.db.query(ServantTripSubscription)
                .filter(
                    ServantTripSubscription.trip_id == trip.id,
                    ServantTripSubscription.teacher_id == teacher.id,
                )
                .all()
            )
        total_charged = sum(
            row.value
            for row in subscriptions
            if row.type == SubscriptionTypeEnum.CHARGE
        )
        total_recovered = sum(
            row.value
            for row in subscriptions
            if row.type == SubscriptionTypeEnum.RECOVER
        )
        total_paid = total_charged - total_recovered
        return ServantTripSummary(
            teacher_id=teacher.id,
            teacher_name=teacher.teacher_name,
            trip_id=trip.id,
            trip_name=trip.name,
            trip_cost=trip.cost,
            total_charged=total_charged,
            total_recovered=total_recovered,
            total_paid=total_paid,
            remaining=trip.cost - total_paid,
            registered=total_charged > 0
            or any(
                row.type == SubscriptionTypeEnum.CHARGE for row in subscriptions
            ),
        )
