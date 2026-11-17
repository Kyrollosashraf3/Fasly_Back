"""اشتراكات الأولاد في الرحلات: مصروف واسترداد لكل ولد في كل رحلة."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, joinedload

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    ensure_boy_access,
    ensure_my_church,
    my_class_ids,
    scope_church,
)
from app.models.boy import Boy
from app.models.enums import RoleEnum, SubscriptionTypeEnum
from app.models.subscription import Subscription
from app.models.trip import Trip
from app.models.user import User
from app.schemas.subscription import (
    BoyTripSummary,
    BoyTripTotal,
    SubscriptionCreate,
    SubscriptionUpdate,
)


class SubscriptionService(BaseService):
    """إدارة اشتراكات الأولاد في الرحلات.

    الصلاحيات:
      - USER (ولد):penas اشتراكاته هو فقط (boy_id == user.boy_id).
      - TEACHER / ADMIN: اشتراكات أولاد فصله فقط.
      - GENERAL_ADMIN: اشتراكات أولاد فصوله.
      - SUPER_ADMIN: كل الولد في كل الفصول.
    """

    # ------------------------------------------------------------- read
    def query(self) -> Query:
        """كل اشتراكات الفصول التي يراها الدخول (مقسمة على الفصل عبر Boy)."""
        q = scope_church(
            self.db.query(Subscription), Subscription, self.user
        ).join(Boy, Subscription.boy_id == Boy.id)
        # A boy login only ever reads his own payments, even inside his class.
        if self.user.role == RoleEnum.USER:
            return q.filter(Subscription.boy_id == self.user.boy_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None:
            q = q.filter(Boy.class_id.in_(mine))
        return q

    @staticmethod
    def _with_names(query: Query) -> Query:
        """Eager-load everything the response names (boy, trip, recorder)."""
        return query.options(
            joinedload(Subscription.boy),
            joinedload(Subscription.trip),
            joinedload(Subscription.creator).joinedload(User.teacher),
            joinedload(Subscription.creator).joinedload(User.boy),
        )

    def list(self) -> list[Subscription]:
        return (
            self._with_names(self.query())
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
            .all()
        )

    def get(self, sub_id: int) -> Subscription:
        sub = self._with_names(self.query()).filter(Subscription.id == sub_id).first()
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الاشتراك غير موجود.",
            )
        return sub

    def get_for_trip(self, trip_id: int) -> list[Subscription]:
        """كل اشتراكات رحلة معينة ضمن نطاق رؤية الدخول."""
        return (
            self._with_names(self.query())
            .filter(Subscription.trip_id == trip_id)
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
            .all()
        )

    # ------------------------------------------------------------- write
    def create(self, data: SubscriptionCreate) -> Subscription:
        boy = self.db.get(Boy, data.boy_id)
        if boy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الولد غير موجود.",
            )
        trip = self.db.get(Trip, data.trip_id)
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الرحلة غير موجودة.",
            )
        # Church first: both ends of the payment must be in the caller's church.
        ensure_boy_access(self.db, self.user, boy)
        ensure_my_church(self.db, self.user, trip.church_id)

        # ----------------------------- الصلاحيات: فقط سوبر أديمن، أديمن، خادم
        if self.user.role not in (RoleEnum.SUPER_ADMIN, RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا يمكنك إضافة اشتراكات. هذه العملية مقتصرة على الأمناء والخادم.",
            )

        # السوبر أديمن غير مقيد بفصل؛ الأديمن والخادم مقيدون بفصلهم فقط
        if self.user.role in (RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            if boy.class_id not in my_class_ids(self.db, self.user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="يمكنك إضافة اشتراكات لأولاد فصلك فقط.",
                )

        # ----------------------------- كشف التكرار (duplicate prevention)
        # لو نفس الولد + نفس الرحلة + نفس المبلغ تم تسجيله خلال الدقيقتين اللي فاتت → ممانش تكرار
        now = datetime.utcnow()
        created_at = data.created_at or now
        duplicate = (
            self.db.query(Subscription)
            .filter(
                Subscription.boy_id == data.boy_id,
                Subscription.trip_id == data.trip_id,
                Subscription.value == data.value,
                Subscription.created_at >= created_at - timedelta(minutes=2),
                Subscription.created_at <= created_at + timedelta(minutes=2),
            )
            .first()
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="تم تسجيل هذا الاشتراك مسبقاً لنفس الولد والرحلة والمبلغ خلال الدقيقتين اللي فاتت.",
            )

        # ----------------------------- validation قبل الحفظ
        # Get boy's summary to check balance
        boy_summary = self.get_boy_trip_summary(trip.id, data.boy_id)

        if data.type == SubscriptionTypeEnum.CHARGE:
            # حالة الدفع: لا يُسمح بمبلغ أكبر من الباقي عليه
            if data.value > boy_summary.remaining:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"المبلغ أكبر من الباقي عليه ({boy_summary.remaining} جنيه).",
                )
        elif data.type == SubscriptionTypeEnum.RECOVER:
            # حالة السحب: لا يُسمح بسحب أكثر مما دفعه الولد مسبقاً (total_charged)
            if data.value > boy_summary.total_charged:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"لا يمكن سحب أكثر من المدفوع مسبقاً ({boy_summary.total_charged} جنيه).",
                )

        sub = Subscription(
            church_id=self.church_for(class_id=boy.class_id, person=boy),
            boy_id=data.boy_id,
            trip_id=data.trip_id,
            type=SubscriptionTypeEnum(data.type),
            value=data.value,
            note=data.note,
            date=data.date or date.today(),
            created_at=created_at,
            created_by=self.user_id,
        )
        self.db.add(sub)
        commit(
            self.db,
            f"Subscription create boy={data.boy_id} trip={data.trip_id}",
        )
        return self.get(sub.id)

    def update(self, sub_id: int, data: SubscriptionUpdate) -> Subscription:
        sub = self.get(sub_id)  # مقسّم على الفصول تلقائيًا

        boy = self.db.get(Boy, sub.boy_id)
        # ----------------------------- الصلاحيات: فقط سوبر أديمن، أديمن، خادم
        if self.user.role not in (RoleEnum.SUPER_ADMIN, RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا يمكنك تعديل اشتراكات. هذه العملية مقتصرة على الأمناء والخادم.",
            )

        # السوبر أديمن غير مقيد بفصل؛ الأديمن والخادم مقيدون بفصلهم فقط
        if self.user.role in (RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            if boy.class_id not in my_class_ids(self.db, self.user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="يمكنك تعديل اشتراكات أولاد فصلك فقط.",
                )

        apply_update(sub, data)
        if data.type is not None:
            sub.type = SubscriptionTypeEnum(data.type)
        commit(self.db, f"Subscription update id={sub_id}")
        return sub

    def delete(self, sub_id: int) -> None:
        sub = self.get(sub_id)  # مقسّم على الفصول تلقائيًا

        # ----------------------------- الصلاحيات: فقط سوبر أديمن، أديمن، خادم
        if self.user.role not in (RoleEnum.SUPER_ADMIN, RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا يمكنك حذف اشتراكات. هذه العملية مقتصرة على الأمناء والخادم.",
            )

        # السوبر أديمن غير مقيد بفصل؛ الأديمن والخادم مقيدون بفصلهم فقط
        if self.user.role in (RoleEnum.ABONA, RoleEnum.ADMIN, RoleEnum.GENERAL_ADMIN, RoleEnum.TEACHER):
            boy = self.db.get(Boy, sub.boy_id)
            if boy.class_id not in my_class_ids(self.db, self.user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="يمكنك حذف اشتراكات أولاد فصلك فقط.",
                )

        self.db.delete(sub)
        commit(self.db, f"Subscription delete id={sub_id}")

    # ------------------------------------------------------------- report
    def get_boy_totals(self, trip_id: int) -> list[BoyTripTotal]:
        """مجموع ما دفعه كل ولد في رحلة (مصروف ناقص استرداد)."""
        trip = self.db.get(Trip, trip_id)
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الرحلة غير موجودة.",
            )

        ensure_my_church(self.db, self.user, trip.church_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None and trip.class_id not in mine:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="يمكنك عرض totals فقط لرحلة فصلك.",
            )

        subs = (
            self.db.query(Subscription)
            .filter(Subscription.trip_id == trip_id)
            .all()
        )
        boys_in_class = (
            self.db.query(Boy)
            .filter(Boy.class_id == trip.class_id)
            .order_by(Boy.boy_name)
            .all()
        )

        totals: dict[int, int] = {b.id: 0 for b in boys_in_class}
        for s in subs:
            if s.type == SubscriptionTypeEnum.CHARGE:
                totals[s.boy_id] = totals.get(s.boy_id, 0) + s.value
            else:
                totals[s.boy_id] = totals.get(s.boy_id, 0) - s.value

        # رجّع فقط الأولاد اللي دفعوا فعلياً (مجموع أكبر من صفر)
        return [
            BoyTripTotal(
                boy_id=b.id,
                boy_name=b.boy_name,
                total_paid=totals.get(b.id, 0),
            )
            for b in boys_in_class
            if totals.get(b.id, 0) > 0
        ]

    # ------------------------------------------------------------- summary (report)
    def _boy_subs_summary(
        self, trip: Trip, boy: Boy, subs: list[Subscription]
    ) -> BoyTripSummary:
        total_charged = 0
        total_recovered = 0
        registered = False
        for s in subs:
            if s.type == SubscriptionTypeEnum.CHARGE:
                # A charge of 0 is a reservation: he owes the whole cost later.
                registered = True
                total_charged += s.value
            else:
                total_recovered += s.value
        total_paid = total_charged - total_recovered
        remaining = trip.cost - total_paid
        return BoyTripSummary(
            boy_id=boy.id,
            boy_name=boy.boy_name,
            trip_id=trip.id,
            trip_name=trip.name,
            trip_cost=trip.cost,
            total_charged=total_charged,
            total_recovered=total_recovered,
            total_paid=total_paid,
            remaining=remaining,
            registered=registered,
        )

    def get_trip_summary(self, trip_id: int) -> list[BoyTripSummary]:
        """ملخص كل أولاد الرحلة: ما دفعه كل ولد والباقي عليه."""
        trip = self.db.get(Trip, trip_id)
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الرحلة غير موجودة.",
            )

        ensure_my_church(self.db, self.user, trip.church_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None and trip.class_id not in mine:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="يمكنك عرض ملخص فقط لرحلة فصلك.",
            )

        subs = (
            self.db.query(Subscription)
            .filter(Subscription.trip_id == trip_id)
            .all()
        )
        boys_in_class = (
            self.db.query(Boy)
            .filter(Boy.class_id == trip.class_id)
            .order_by(Boy.boy_name)
            .all()
        )

        # group subs by boy
        subs_by_boy: dict[int, list[Subscription]] = {}
        for s in subs:
            subs_by_boy.setdefault(s.boy_id, []).append(s)

        return [
            self._boy_subs_summary(trip, b, subs_by_boy.get(b.id, []))
            for b in boys_in_class
        ]

    def get_boy_trip_summary(self, trip_id: int, boy_id: int) -> BoyTripSummary:
        """ملخص ولد واحد في رحلة واحدة: دفع كام وباقي كام."""
        trip = self.db.get(Trip, trip_id)
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الرحلة غير موجودة.",
            )
        boy = self.db.get(Boy, boy_id)
        if boy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الولد غير موجود.",
            )

        ensure_my_church(self.db, self.user, trip.church_id)
        mine = my_class_ids(self.db, self.user)
        if mine is not None and trip.class_id not in mine:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="يمكنك عرض ملخص فقط لرحلة فصلك.",
            )

        # USER: يرى ملخصه هو فقط
        if self.user.role == RoleEnum.USER and boy.id != self.user.boy_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا يمكنك عرض ملخص إلا لنفسك.",
            )
        elif self.user.role in (
            RoleEnum.TEACHER,
            RoleEnum.ADMIN,
            RoleEnum.GENERAL_ADMIN,
            RoleEnum.ABONA,
        ):
            if boy.class_id not in mine:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="يمكنك عرض ملخص فقط لأولاد فصلك.",
                )

        subs = (
            self.db.query(Subscription)
            .filter(Subscription.trip_id == trip_id, Subscription.boy_id == boy_id)
            .all()
        )
        return self._boy_subs_summary(trip, boy, subs)

