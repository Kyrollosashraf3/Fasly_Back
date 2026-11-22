"""Idempotent demonstration data for two isolated churches."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status

from app.core.auth.security import get_password_hash
from app.core.data.base import BaseService
from app.models.attend import Attend
from app.models.boy import Boy
from app.models.church import Church
from app.models.enums import (
    FollowEnum,
    GenderEnum,
    RoleEnum,
    SubscriptionTypeEnum,
)
from app.models.follow_up import FollowUp
from app.models.group import Group
from app.models.school_class import SchoolClass
from app.models.subscription import Subscription
from app.models.task import Task
from app.models.task_value import TaskValue
from app.models.teacher import Teacher
from app.models.trip import Trip
from app.models.trip_attendance import TripAttendance
from app.models.user import User


class SeedService(BaseService):
    def seed(self) -> dict:
        if self.user.role != RoleEnum.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط أدمن عام يقدر ينشئ بيانات التجربة.",
            )

        password_hash = get_password_hash("123456")
        today = date.today()
        counts = {
            "churches": 0,
            "classes": 0,
            "teachers": 0,
            "boys": 0,
            "users": 0,
            "groups": 0,
            "followups": 0,
            "attendance": 0,
            "trips": 0,
            "subscriptions": 0,
            "tasks": 0,
            "task_values": 0,
            "trip_attendance": 0,
        }

        tenant_specs = [
            {
                "name": "كنيسة الشهيد مارجرجس",
                "region": "القاهرة",
                "address": "القاهرة",
                "phone": "01000000001",
                "church_code": "1",
                "coords": (30.0444, 31.2357),
            },
            {
                "name": "كنيسة القديس العظيم مرقس",
                "region": "الإسكندرية",
                "address": "الإسكندرية",
                "phone": "01000000002",
                "church_code": "2",
                "coords": (31.2001, 29.9187),
            },
        ]

        for church_index, spec in enumerate(tenant_specs):
            church = (
                self.db.query(Church)
                .filter(Church.name == spec["name"])
                .first()
            )
            if church is None:
                church = Church(
                    name=spec["name"],
                    region=spec["region"],
                    address=spec["address"],
                    phone=spec["phone"],
                    is_active=True,
                )
                self.db.add(church)
                self.db.flush()
                counts["churches"] += 1

            abona_phone = f"01000000{spec['church_code']}00"
            abona = self.db.query(Teacher).filter(
                Teacher.phone == abona_phone,
                Teacher.church_id == church.id,
            ).first()
            if abona is None:
                abona = Teacher(
                    teacher_name=f"أبونا كنيسة {church_index + 1}",
                    phone=abona_phone,
                    class_id=None,
                    church_id=church.id,
                    zone=spec["region"],
                    address=spec["address"],
                )
                self.db.add(abona)
                self.db.flush()
                counts["teachers"] += 1
            abona_user = self.db.query(User).filter(User.phone == abona_phone).first()
            if abona_user is None:
                abona_user = User(
                    phone=abona_phone,
                    password_hash=password_hash,
                    role=RoleEnum.ABONA,
                    church_id=church.id,
                    teacher_id=abona.id,
                )
                self.db.add(abona_user)
                self.db.flush()
                counts["users"] += 1

            class_specs = [
                ("ابتدائي", today.year if today.month >= 9 else today.year - 1),
                ("إعدادي", today.year if today.month >= 9 else today.year - 1),
            ]
            for class_index, (class_name, year_start) in enumerate(class_specs):
                class_record = (
                    self.db.query(SchoolClass)
                    .filter(
                        SchoolClass.church_id == church.id,
                        SchoolClass.name == class_name,
                    )
                    .first()
                )
                if class_record is None:
                    class_record = SchoolClass(
                        name=class_name,
                        academic_year=f"{year_start}/{year_start + 1}",
                        church_id=church.id,
                    )
                    self.db.add(class_record)
                    self.db.flush()
                    counts["classes"] += 1

                teacher_phone = f"0100000{church_index + 1}{class_index + 1}00"
                teacher = (
                    self.db.query(Teacher)
                    .filter(Teacher.phone == teacher_phone, Teacher.church_id == church.id)
                    .first()
                )
                if teacher is None:
                    teacher = Teacher(
                        teacher_name=f"خادم {class_name} {church_index + 1}",
                        phone=teacher_phone,
                        class_id=class_record.id,
                        church_id=church.id,
                        zone=spec["region"],
                        address=spec["address"],
                        latitude=spec["coords"][0] + 0.002 * class_index,
                        longitude=spec["coords"][1] + 0.002 * class_index,
                    )
                    self.db.add(teacher)
                    self.db.flush()
                    counts["teachers"] += 1

                teacher_user = self.db.query(User).filter(User.phone == teacher_phone).first()
                if teacher_user is None:
                    teacher_user = User(
                        phone=teacher_phone,
                        password_hash=password_hash,
                        role=RoleEnum.TEACHER,
                        church_id=church.id,
                        teacher_id=teacher.id,
                    )
                    self.db.add(teacher_user)
                    self.db.flush()
                    counts["users"] += 1

                for boy_index in range(3):
                    boy_name = f"ولد {boy_index + 1} - {class_name} - كنيسة {church_index + 1}"
                    boy = (
                        self.db.query(Boy)
                        .filter(Boy.boy_name == boy_name, Boy.church_id == church.id)
                        .first()
                    )
                    if boy is None:
                        boy = Boy(
                            boy_name=boy_name,
                            gender=GenderEnum.MALE,
                            birth_date=date(2012 - class_index, 4, 10 + boy_index),
                            phone=f"011000{church_index + 1}{class_index + 1}{boy_index}",
                            phone_2=f"010111{church_index + 1}{class_index + 1}{boy_index}",
                            zone=spec["region"],
                            address=f"عنوان تجريبي {boy_index + 1}",
                            latitude=spec["coords"][0] + 0.003 * (boy_index + 1),
                            longitude=spec["coords"][1] + 0.003 * (boy_index + 1),
                            class_id=class_record.id,
                            church_id=church.id,
                            issue_flag=boy_index == 2,
                        )
                        self.db.add(boy)
                        self.db.flush()
                        counts["boys"] += 1

                    group = (
                        self.db.query(Group)
                        .filter(Group.teacher_id == teacher.id, Group.boy_id == boy.id)
                        .first()
                    )
                    if group is None:
                        self.db.add(Group(
                            church_id=church.id,
                            teacher_id=teacher.id,
                            boy_id=boy.id,
                        ))
                        counts["groups"] += 1

                    boy_phone = boy.phone
                    boy_user = self.db.query(User).filter(User.phone == boy_phone).first()
                    if boy_user is None:
                        self.db.add(User(
                            phone=boy_phone,
                            password_hash=password_hash,
                            role=RoleEnum.USER,
                            church_id=church.id,
                            boy_id=boy.id,
                        ))
                        counts["users"] += 1

                    for day_offset in (0, -7, -14):
                        action_date = today + timedelta(days=day_offset)
                        attend = (
                            self.db.query(Attend)
                            .filter(Attend.boy_id == boy.id, Attend.date == action_date)
                            .first()
                        )
                        if attend is None:
                            self.db.add(Attend(
                                church_id=church.id,
                                class_id=class_record.id,
                                boy_id=boy.id,
                                date=action_date,
                                present=boy_index != 2,
                                liturgy=boy_index == 0,
                                recorded_by=teacher_user.id,
                            ))
                            counts["attendance"] += 1

                    followup_date = today - timedelta(days=7 - boy_index)
                    followup = (
                        self.db.query(FollowUp)
                        .filter(
                            FollowUp.boy_id == boy.id,
                            FollowUp.action_date == followup_date,
                        )
                        .first()
                    )
                    if followup is None:
                        self.db.add(FollowUp(
                            church_id=church.id,
                            class_id=class_record.id,
                            teacher_id=teacher.id,
                            boy_id=boy.id,
                            action_date=followup_date,
                            status=FollowEnum.VISIT if boy_index != 1 else FollowEnum.CALL,
                            note="افتقاد تجريبي",
                            recorded_by=teacher_user.id,
                        ))
                        counts["followups"] += 1

                trip = (
                    self.db.query(Trip)
                    .filter(Trip.name == f"رحلة فصل {class_name}", Trip.church_id == church.id)
                    .first()
                )
                if trip is None:
                    trip = Trip(
                        name=f"رحلة فصل {class_name}",
                        cost=300,
                        class_id=class_record.id,
                        church_id=church.id,
                        created_at=today,
                        status="active",
                        recorded_by=teacher_user.id,
                    )
                    self.db.add(trip)
                    self.db.flush()
                    counts["trips"] += 1

                boys = self.db.query(Boy).filter(Boy.class_id == class_record.id).all()
                for boy in boys:
                    existing_subscription = (
                        self.db.query(Subscription)
                        .filter(
                            Subscription.trip_id == trip.id,
                            Subscription.boy_id == boy.id,
                            Subscription.type == SubscriptionTypeEnum.CHARGE,
                        )
                        .first()
                    )
                    if existing_subscription is None:
                        self.db.add(Subscription(
                            church_id=church.id,
                            boy_id=boy.id,
                            trip_id=trip.id,
                            type=SubscriptionTypeEnum.CHARGE,
                            value=100,
                            date=today,
                            created_by=teacher_user.id,
                            note="دفعة تجريبية",
                        ))
                        counts["subscriptions"] += 1
                    existing_trip_attendance = (
                        self.db.query(TripAttendance)
                        .filter(
                            TripAttendance.trip_id == trip.id,
                            TripAttendance.boy_id == boy.id,
                        )
                        .first()
                    )
                    if existing_trip_attendance is None:
                        self.db.add(TripAttendance(
                            church_id=church.id,
                            trip_id=trip.id,
                            boy_id=boy.id,
                            teacher_id=teacher.id,
                            attend_flag=True,
                        ))
                        counts["trip_attendance"] += 1

                task = (
                    self.db.query(Task)
                    .filter(Task.task_name == f"حفظ أناشيد {class_name}", Task.church_id == church.id)
                    .first()
                )
                if task is None:
                    task = Task(
                        task_name=f"حفظ أناشيد {class_name}",
                        value=25,
                        class_id=class_record.id,
                        church_id=church.id,
                        created_at=today,
                        status="active",
                    )
                    self.db.add(task)
                    self.db.flush()
                    counts["tasks"] += 1

                for boy in boys:
                    task_value = (
                        self.db.query(TaskValue)
                        .filter(TaskValue.task_id == task.id, TaskValue.boy_id == boy.id)
                        .first()
                    )
                    if task_value is None:
                        self.db.add(TaskValue(
                            church_id=church.id,
                            class_id=class_record.id,
                            task_id=task.id,
                            boy_id=boy.id,
                            action_date=today,
                            received=True,
                            created_by=teacher.id,
                        ))
                        counts["task_values"] += 1

        self.db.commit()
        return {"ok": True, "message": "تم إنشاء بيانات التجربة لكل الكنائس.", "counts": counts}
