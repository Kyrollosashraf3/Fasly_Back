"""Trips (الرحلات) - اشتراكات الفصول في الرحلات."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    is_unrestricted,
    owner_class_id,
)
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripUpdate


class TripService(BaseService):
    """القراءة مقسمة على الفصول.

    الكتابة:
      - الخادم / أمين الفصل يضيف رحلة لفصله فقط (يُفرض ``class_id``).
      - أمين المرحلة يضيف رحلة لأي فصل من فصوله.
      - أمين الكنيسة (سوبر أدمن) يختار أي班 عبر ``class_id``.
      - تسجيل الدخول الخاص بولد (user) مرفوض完全ًا.
    """

    def query(self) -> Query:
        return self.classes_query(Trip)

    def list(
        self,
        status: str | None = 'active',
        class_id: int | None = None,
    ) -> list[Trip]:
        """Trips in scope, newest first.

        ``status`` defaults to the active trips the module is about; the amin
        can ask for ``inactive`` to revisit an old trip. ``class_id`` narrows
        the catalogue to one class (a super admin choosing a class filter).
        """
        query = self.query()
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Trip.class_id == class_id)
        if status in ('active', 'inactive'):
            query = query.filter(Trip.status == status)
        return query.order_by(Trip.created_at.desc(), Trip.id.desc()).all()

    def get(self, trip_id: int) -> Trip:
        trip = self.query().filter(Trip.id == trip_id).first()
        if trip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الرحلة غير موجودة.",
            )
        return trip

    def create(self, data: TripCreate) -> Trip:
        if self.user.role == RoleEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مسموح لك بإضافة رحلة.",
            )

        # الخادم أو أمين الفصل: تُفرض الرحلة على فصله فقط
        if self.user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
            my_class = owner_class_id(self.db, self.user)
            if my_class is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="لا يوجد فصل مرتبط بحسابك.",
                )
            effective_class_id = my_class
        else:
            # أمين الكنيسة: يحتفظ بالقيمة التي أرسلها (أي班)
            # أمين المرحلة: نفس القيمة، ما دامت جوه فصوله
            effective_class_id = data.class_id
            if not is_unrestricted(self.user):
                self.ensure_class(effective_class_id)

        self._ensure_class(effective_class_id)
        self._ensure_no_duplicate(
            data.name.strip(),
            data.created_at or date.today(),
            effective_class_id,
        )
        trip = Trip(
            name=data.name.strip(),
            cost=data.cost,
            church_id=self.church_for(class_id=effective_class_id),
            class_id=effective_class_id,
            created_at=data.created_at or date.today(),
            status=data.status or 'active',
            recorded_by=self.user_id,
        )
        self.db.add(trip)
        commit(self.db, f"Trip create name={data.name}")
        return trip

    def update(self, trip_id: int, data: TripUpdate) -> Trip:
        trip = self.get(trip_id)  # مقسّم على الفصول تلقائيًا

        new_name = (data.name or "").strip()
        new_date = data.created_at if data.created_at is not None else trip.created_at
        new_class_id = data.class_id if data.class_id is not None else trip.class_id

        if self.user.role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
            # لا يسمح بنقل رحلة لفصل آخر
            if data.class_id is not None and data.class_id != trip.class_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="غير مسموح لك بنقل رحلة لفصل آخر.",
                )
        elif data.class_id is not None:
            # أمين الكنيسة قد يغيّر الفصل لأي班 موجود، أمين المرحلة لفصوله فقط
            self._ensure_class(data.class_id)
            if not is_unrestricted(self.user):
                self.ensure_class(data.class_id)

        # إذا تغيّر الاسم أو تاريخ التسجيل أو الفصل، تأكد من عدم تكرار الرحلة
        if (new_name, new_date, new_class_id) != (
            trip.name,
            trip.created_at,
            trip.class_id,
        ):
            self._ensure_no_duplicate(
                new_name, new_date, new_class_id, exclude_id=trip_id
            )

        apply_update(trip, data, strip=("name",))
        commit(self.db, f"Trip update id={trip_id}")
        return trip

    def delete(self, trip_id: int) -> None:
        trip = self.get(trip_id)  # مقسّم على الفصول تلقائيًا
        self.db.delete(trip)
        commit(self.db, f"Trip delete id={trip_id}")

    def _ensure_class(self, class_id: int) -> None:
        school_class = self.db.get(SchoolClass, class_id)
        if school_class is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الفصل غير موجود.",
            )

    def _ensure_no_duplicate(
        self,
        name: str,
        created_at: date,
        class_id: int,
        exclude_id: int | None = None,
    ) -> None:
        """يمنع رحلة مكررة: نفس الاسم، نفس قيمة الاشتراك، نفس التاريخ، نفس الفصل.

        لو اختلف الفصل عن رحلة موجودة بنفس الاسم والتكلفة والتاريخ، تُعتبر رحلة جديدة.
        """
        query = self.db.query(Trip).filter(
            Trip.name == name,
            Trip.created_at == created_at,
            Trip.class_id == class_id,
        )
        if exclude_id is not None:
            query = query.filter(Trip.id != exclude_id)
        if query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رحلة بهذا الاسم والتاريخ موجودة بالفعل لنفس الفصل.",
            )