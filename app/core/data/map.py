"""The home-visit map: houses, contact shortcuts, and a walk route.

The server owns the permissions and the maths; the map library in the frontend
only draws ``polyline`` and puts markers on ``houses``. Everything needed to
open the follow-up panel after tapping (+) is in ``prefill``. A house's pin is
simply ``boys.latitude`` / ``boys.longitude`` - no second location table.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.core.data.base import BaseService
from app.core.data.common import (
    STAFF,
    ensure_teacher_access,
    get_or_404,
    my_class_ids,
    scope_boys,
    scope_church,
)
from app.core.geo import haversine_m, nearest_neighbour, walk_minutes
from app.models.boy import Boy
from app.models.enums import FollowEnum, RoleEnum
from app.models.follow_up import FollowUp
from app.models.group import Group
from app.models.teacher import Teacher
from app.schemas.location import (
    FOLLOW_UP_STATUS_OPTIONS,
    FollowUpPrefill,
    MapHouse,
    MapLeg,
    MapOrigin,
    MapRouteResponse,
    MapScopeEnum,
    MapSummary,
)

SCOPE_LABELS = {
    MapScopeEnum.GROUP: "مجموعتي فقط",
    MapScopeEnum.CLASS: "الفصل كله",
    MapScopeEnum.ALL: "كل الفصول المسموحة",
}


def _digits(phone: str) -> str:
    """Turn ``0101...`` / ``+20 101...`` into ``20101...`` for deep links."""
    value = "".join(char for char in phone if char.isdigit())
    if value.startswith("00"):
        return value[2:]
    if value.startswith("0"):
        return "20" + value[1:]
    return value


class VisitMapService(BaseService):
    """read : the same boy scopes as the rest of the app (a boy: his own house)"""

    def route(
        self,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        scope: MapScopeEnum = MapScopeEnum.CLASS,
        teacher_id: int | None = None,
        class_id: int | None = None,
        name: str | None = None,
        zone: str | None = None,
        address: str | None = None,
    ) -> MapRouteResponse:
        boys = (
            self._boys_query(scope, teacher_id, class_id, name, zone, address)
            .options(
                joinedload(Boy.class_),
                joinedload(Boy.groups).joinedload(Group.teacher),
            )
            .order_by(Boy.boy_name)
            .all()
        )
        ids = [boy.id for boy in boys]
        stats, visited_today = self._follow_up_stats(ids)

        houses = [self._house(boy, stats.get(boy.id, {}), teacher_id) for boy in boys]
        located = [house for house in houses if house.has_coordinates]
        unlocated = [house for house in houses if not house.has_coordinates]

        origin, legs, ordered, polyline = self._route_points(latitude, longitude, located)

        located_count = len(located)
        summary = MapSummary(
            total_boys=len(houses),
            located=located_count,
            unlocated=len(unlocated),
            visited_today=visited_today,
            coverage_percent=round(100 * located_count / len(houses), 1) if houses else 0.0,
        )
        total_m = sum(leg.distance_m for leg in legs)

        return MapRouteResponse(
            scope=scope,
            scope_label=SCOPE_LABELS[scope],
            teacher_id=teacher_id or self.user.teacher_id,
            class_ids=my_class_ids(self.db, self.user),
            origin=origin,
            houses=ordered,
            unlocated=unlocated,
            legs=legs,
            polyline=polyline,
            ordered_boy_ids=[house.boy_id for house in ordered],
            total_distance_m=total_m,
            total_distance_km=round(total_m / 1000, 2),
            total_walk_minutes=sum(leg.walk_minutes for leg in legs),
            summary=summary,
            follow_up_status_options=FOLLOW_UP_STATUS_OPTIONS,
            generated_at=datetime.now(timezone.utc),
        )

    # -------------------------------------------------------------- internals
    def _boys_query(self, scope, teacher_id, class_id, name, zone, address):
        """The filtered boy list; scope-out never leaks another class's house."""
        if self.user.role == RoleEnum.USER:
            query = self.db.query(Boy).filter(Boy.id == self.user.boy_id)
        elif scope == MapScopeEnum.GROUP:
            group_teacher_id = teacher_id or self.user.teacher_id
            if group_teacher_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No group is linked to this account. A servant log-in, "
                        "or the teacher_id query parameter, is required for scope=group."
                    ),
                )
            teacher = get_or_404(self.db, Teacher, group_teacher_id, "Servant")
            ensure_teacher_access(self.db, self.user, teacher)
            boy_ids = [
                row[0]
                for row in self.db.query(Group.boy_id).filter(
                    Group.teacher_id == teacher.id
                )
            ]
            # Tenant first: a group row is not proof the boy is in this church.
            query = scope_church(self.db.query(Boy), Boy, self.user).filter(
                Boy.id.in_(boy_ids)
            )
        else:
            query = scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)

        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Boy.class_id == class_id)
        if name and name.strip():
            query = query.filter(Boy.boy_name.ilike(self._like(name.strip()), escape="!"))
        if zone and zone.strip():
            area_pattern = self._like(zone.strip())
            query = query.filter(
                or_(
                    Boy.zone.ilike(area_pattern, escape="!"),
                    Boy.address.ilike(area_pattern, escape="!"),
                )
            )
        if address and address.strip():
            query = query.filter(Boy.address.ilike(self._like(address.strip()), escape="!"))
        return query

    @staticmethod
    def _like(value: str) -> str:
        """Escape user-supplied LIKE metacharacters while keeping substring search."""
        escaped = value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        return f"%{escaped}%"

    def _follow_up_stats(self, ids: list[int]) -> tuple[dict[int, dict], int]:
        if not ids:
            return {}, 0
        rows = (
            self.db.query(FollowUp.boy_id, FollowUp.action_date, FollowUp.status)
            .filter(FollowUp.boy_id.in_(ids))
            .order_by(FollowUp.action_date.desc(), FollowUp.id.desc())
            .all()
        )
        stats: dict[int, dict] = {}
        visited_today = 0
        today = date.today()
        for boy_id, action_date, status in rows:
            item = stats.setdefault(boy_id, {"date": None, "status": None, "count": 0})
            if item["date"] is None:
                item["date"], item["status"] = action_date, status
            item["count"] += 1
            if action_date == today and status == FollowEnum.VISIT:
                visited_today += 1
        return stats, visited_today

    def _house(self, boy, stat, teacher_id) -> MapHouse:
        phones = [value for value in (boy.phone, boy.phone_2) if value]
        number = _digits(phones[0]) if phones else ""

        prefill_teacher = (
            teacher_id
            or (self.user.teacher_id if self.user.role in STAFF else None)
            or boy.teacher_id
        )
        prefill = FollowUpPrefill(
            teacher_id=prefill_teacher,
            boy_id=boy.id,
            status=FollowEnum.VISIT,
            action_date=date.today(),
        )

        return MapHouse(
            boy_id=boy.id,
            boy_name=boy.boy_name,
            gender=boy.gender,
            class_id=boy.class_id,
            class_name=boy.class_.name if boy.class_ else "",
            teacher_id=boy.teacher_id,
            teacher_name=boy.teacher_name,
            latitude=boy.latitude,
            longitude=boy.longitude,
            has_coordinates=boy.latitude is not None and boy.longitude is not None,
            zone=boy.zone,
            address=boy.address,
            phone=boy.phone,
            phone_2=boy.phone_2,
            whatsapp_url=f"https://wa.me/{number}" if number else None,
            call_url=f"tel:+{number}" if number else None,
            last_follow_up_date=stat.get("date"),
            last_follow_up_status=stat.get("status"),
            follow_up_count=stat.get("count", 0),
            prefill=prefill,
            can_record_location=True,
            can_follow_up=self.user.role in STAFF,
        )

    def _route_points(self, latitude, longitude, located):
        """Order the houses nearest-first and build the drawable line."""
        points = [
            (house.boy_id, house.latitude, house.longitude) for house in located
        ]
        if latitude is None or longitude is None:
            if not points:
                return None, [], [], []
            start = (points[0][1], points[0][2])
            origin = MapOrigin(
                latitude=start[0], longitude=start[1], source="first_house"
            )
        else:
            start = (latitude, longitude)
            origin = MapOrigin(latitude=latitude, longitude=longitude, source="client")

        ordered_points = nearest_neighbour(start, points)
        by_id = {house.boy_id: house for house in located}
        ordered = [by_id[boy_id] for boy_id, _, _ in ordered_points]

        legs = []
        previous = start
        previous_boy_id = None
        for order, (boy_id, lat, lng) in enumerate(ordered_points, 1):
            distance = haversine_m(previous, (lat, lng))
            legs.append(
                MapLeg(
                    order=order,
                    from_boy_id=previous_boy_id,
                    from_latitude=previous[0],
                    from_longitude=previous[1],
                    to_boy_id=boy_id,
                    to_latitude=lat,
                    to_longitude=lng,
                    distance_m=round(distance),
                    distance_km=round(distance / 1000, 3),
                    walk_minutes=walk_minutes(distance),
                )
            )
            previous, previous_boy_id = (lat, lng), boy_id

        polyline = [[start[0], start[1]]] + [
            [lat, lng] for _, lat, lng in ordered_points
        ]
        return origin, legs, ordered, polyline
