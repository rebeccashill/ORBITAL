# mission_framework/aircraft/geofence.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


Point = Tuple[float, float]


def point_in_polygon(p: Point, poly: Sequence[Point]) -> bool:
    """Ray casting algorithm (works for simple polygons)."""
    x, y = p
    inside = False
    n = len(poly)
    if n < 3:
        return False
    x0, y0 = poly[-1]
    for x1, y1 in poly:
        cond = ((y1 > y) != (y0 > y)) and (x < (x0 - x1) * (y - y1) / ((y0 - y1) or 1e-12) + x1)
        if cond:
            inside = not inside
        x0, y0 = x1, y1
    return inside


@dataclass(frozen=True)
class NoFlyZone:
    zone_id: str
    polygon: List[Point]


@dataclass(frozen=True)
class GeofenceMap:
    zones: List[NoFlyZone]

    def is_violation(self, x_m: float, y_m: float) -> bool:
        p = (float(x_m), float(y_m))
        return any(point_in_polygon(p, z.polygon) for z in self.zones)
