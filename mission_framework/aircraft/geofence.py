# mission_framework/aircraft/geofence.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Dict, Any

import math

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def point_in_polygon(p: Point, poly: Sequence[Point]) -> bool:
    """Ray casting algorithm (works for simple polygons)."""
    x, y = p
    inside = False
    n = len(poly)
    if n < 3:
        return False
    x0, y0 = poly[-1]
    for x1, y1 in poly:
        # avoid divide-by-zero on horizontal edges
        denom = (y0 - y1) if (y0 - y1) != 0 else 1e-12
        cond = ((y1 > y) != (y0 > y)) and (x < (x0 - x1) * (y - y1) / denom + x1)
        if cond:
            inside = not inside
        x0, y0 = x1, y1
    return inside


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    """True if c is on segment ab (collinear assumed)."""
    return (
        min(a[0], b[0]) - 1e-12 <= c[0] <= max(a[0], b[0]) + 1e-12
        and min(a[1], b[1]) - 1e-12 <= c[1] <= max(a[1], b[1]) + 1e-12
    )


def segments_intersect(s1: Segment, s2: Segment) -> bool:
    """Proper segment intersection test (incl collinear overlap)."""
    a, b = s1
    c, d = s2
    o1 = _orient(a, b, c)
    o2 = _orient(a, b, d)
    o3 = _orient(c, d, a)
    o4 = _orient(c, d, b)

    # General case
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True

    # Collinear cases
    eps = 1e-12
    if abs(o1) < eps and _on_segment(a, b, c):
        return True
    if abs(o2) < eps and _on_segment(a, b, d):
        return True
    if abs(o3) < eps and _on_segment(c, d, a):
        return True
    if abs(o4) < eps and _on_segment(c, d, b):
        return True

    return False


def polygon_edges(poly: Sequence[Point]) -> List[Segment]:
    if len(poly) < 2:
        return []
    edges: List[Segment] = []
    prev = poly[-1]
    for cur in poly:
        edges.append((prev, cur))
        prev = cur
    return edges


def point_to_segment_distance(p: Point, seg: Segment) -> float:
    """Euclidean distance from point to segment."""
    x, y = p
    (x1, y1), (x2, y2) = seg
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(x - x1, y - y1)

    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projx = x1 + t * dx
    projy = y1 + t * dy
    return math.hypot(x - projx, y - projy)


def point_to_polygon_boundary_distance(p: Point, poly: Sequence[Point]) -> float:
    """Minimum distance from point to polygon boundary edges."""
    edges = polygon_edges(poly)
    if not edges:
        return float("inf")
    return min(point_to_segment_distance(p, e) for e in edges)


@dataclass(frozen=True)
class NoFlyZone:
    zone_id: str
    polygon: List[Point]


@dataclass(frozen=True)
class GeofenceHit:
    zone_id: str
    index: int
    point: Point
    kind: str  # "inside" or "crossing"


@dataclass(frozen=True)
class GeofenceAudit:
    violated: bool
    hits: List[GeofenceHit]
    min_clearance_m: float
    min_clearance_index: Optional[int]
    min_clearance_point: Optional[Point]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class GeofenceMap:
    zones: List[NoFlyZone]

    def is_violation_point(self, x_m: float, y_m: float) -> bool:
        p = (float(x_m), float(y_m))
        return any(point_in_polygon(p, z.polygon) for z in self.zones)

    def audit_trajectory(
        self,
        xs_m: Sequence[float],
        ys_m: Sequence[float],
        clearance_m: float = 0.0,
    ) -> GeofenceAudit:
        """
        Trajectory-level geofence audit.

        - Flags if any sample point is inside a no-fly polygon
        - Flags if any segment crosses polygon boundary (even if samples don't land inside)
        - Computes minimum clearance to any zone boundary (useful for 'keep-out buffer')
          margin for constraints can be: min_clearance_m - clearance_m
        """
        x = [float(v) for v in xs_m]
        y = [float(v) for v in ys_m]
        if len(x) != len(y):
            raise ValueError("xs_m and ys_m must have same length.")
        n = len(x)
        hits: List[GeofenceHit] = []

        # Track min clearance across all points to all zone boundaries
        min_clear = float("inf")
        min_idx: Optional[int] = None
        min_pt: Optional[Point] = None

        # Precompute segments
        segs: List[Segment] = []
        for i in range(n - 1):
            segs.append(((x[i], y[i]), (x[i + 1], y[i + 1])))

        for i in range(n):
            p = (x[i], y[i])
            for z in self.zones:
                # inside check
                if point_in_polygon(p, z.polygon):
                    hits.append(GeofenceHit(zone_id=z.zone_id, index=i, point=p, kind="inside"))

                # clearance to boundary
                d = point_to_polygon_boundary_distance(p, z.polygon)
                if d < min_clear:
                    min_clear = d
                    min_idx = i
                    min_pt = p

        # crossing check (segment intersects polygon boundary)
        for i, s in enumerate(segs):
            for z in self.zones:
                for edge in polygon_edges(z.polygon):
                    if segments_intersect(s, edge):
                        hits.append(
                            GeofenceHit(zone_id=z.zone_id, index=i, point=s[0], kind="crossing")
                        )
                        break

        violated = len(hits) > 0 or (min_clear < float(clearance_m))

        return GeofenceAudit(
            violated=violated,
            hits=hits,
            min_clearance_m=float(min_clear),
            min_clearance_index=min_idx,
            min_clearance_point=min_pt,
            metadata={
                "clearance_required_m": float(clearance_m),
                "num_points": n,
                "num_zones": len(self.zones),
            },
        )
