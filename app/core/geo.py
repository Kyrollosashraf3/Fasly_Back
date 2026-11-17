"""Tiny, dependency-free geography helpers used by the visit map.

No external geocoding/routing service: the points are already known, so the
route is a nearest-neighbour walk over the haversine distance. The frontend
only draws the returned polyline.
"""

from __future__ import annotations

from math import atan2, ceil, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000
WALK_METRES_PER_MINUTE = 5_000 / 60  # ~5 km/h


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line distance in metres between two ``(lat, lng)`` points."""
    lat1, lng1 = radians(a[0]), radians(a[1])
    lat2, lng2 = radians(b[0]), radians(b[1])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(h), sqrt(1 - h))


def walk_minutes(distance_m: float) -> int:
    """Rounded-up walking time for a leg, in minutes."""
    return max(1, ceil(distance_m / WALK_METRES_PER_MINUTE)) if distance_m else 0


def nearest_neighbour(
    origin: tuple[float, float],
    points: list[tuple[int, float, float]],
) -> list[tuple[int, float, float]]:
    """Order ``(boy_id, lat, lng)`` stops: closest to the current point first.

    Greedy on purpose - easy to read, deterministic, and good enough for a
    handful of houses in one church district.
    """
    remaining = list(points)
    ordered: list[tuple[int, float, float]] = []
    here = origin
    while remaining:
        nearest = min(remaining, key=lambda p: haversine_m(here, (p[1], p[2])))
        ordered.append(nearest)
        remaining.remove(nearest)
        here = (nearest[1], nearest[2])
    return ordered
