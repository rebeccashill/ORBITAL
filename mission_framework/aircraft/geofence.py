# mission_framework/aircraft/geofence.py
"""
Polygon no-fly zones (geofences) (MODULE A / aircraft).

Provides:
- Polygon representation (2D)
- Point-in-polygon test
- Segment intersection / "path crosses geofence" checks
- Minimal distance-to-boundary utility (approx)

Coordinates:
- Uses a flat-earth 2D plane: (x, y) in meters (or any consistent planar units).
- If you have lat/lon, project to local ENU/NED before using these utilities.

Conventions:
- A geofence polygon describes a "no-fly" region (inside polygon is forbidden).
- Holes are not supported in this simple implementation (can be added later).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import math


Point2 = Tuple[float, float]


# ============================================================
# Helpers
# ============================================================

def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _sub(a: Point2, b: Point2) -> Point2:
    return (a[0] - b[0], a[1] - b[1])


def _dot(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _norm(a: Point2) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1])


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _dist_point_to_segment(p: Point2, a: Point2, b: Point2) -> float:
    """Euclidean distance from p to segment ab."""
    ab = _sub(b, a)
    ap = _sub(p, a)
    denom = _dot(ab, ab)
    if denom <= 1e-12:
        return _norm(_sub(p, a))
    t = _clamp(_dot(ap, ab) / denom, 0.0, 1.0)
    proj = (a[0] + t * ab[0], a[1] + t * ab[1])
    return _norm(_sub(p, proj))


def _on_segment(p: Point2, a: Point2, b: Point2, eps: float = 1e-9) -> bool:
    """Check if point p lies on segment ab (with tolerance)."""
    ap = _sub(p, a)
    ab = _sub(b, a)
    cross = _cross(ap[0], ap[1], ab[0], ab[1])
    if abs(cross) > eps:
        return False
    dot = _dot(ap, ab)
    if dot < -eps:
        return False
    if dot > _dot(ab, ab) + eps:
        return False
    return True


def _segments_intersect(a1: Point2, a2: Point2, b1: Point2, b2: Point2, eps: float = 1e-9) -> bool:
    """Robust-ish 2D segment intersection, including collinear overlap."""
    def orient(p: Point2, q: Point2, r: Point2) -> float:
        return _cross(q[0] - p[0], q[1] - p[1], r[0] - p[0], r[1] - p[1])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)

    # General case
    if (o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps):
        if (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps):
            return True

    # Collinear / endpoint touching
    if abs(o1) <= eps and _on_segment(b1, a1, a2, eps):
        return True
    if abs(o2) <= eps and _on_segment(b2, a1, a2, eps):
        return True
    if abs(o3) <= eps and _on_segment(a1, b1, b2, eps):
        return True
    if abs(o4) <= eps and _on_segment(a2, b1, b2, eps):
        return True

    return False


# ============================================================
# Geofence polygon
# ============================================================

@dataclass(frozen=True)
class PolygonFence:
    """
    A simple closed polygon geofence.

    vertices:
        sequence of (x, y) points. Polygon is assumed closed (last connects to first).
    name:
        optional identifier (useful for reporting constraint violations).
    """
    vertices: Tuple[Point2, ...]
    name: str = "geofence"

    def __post_init__(self):
        if len(self.vertices) < 3:
            raise ValueError("PolygonFence must have at least 3 vertices.")

    def edges(self) -> List[Tuple[Point2, Point2]]:
        vs = list(self.vertices)
        return list(zip(vs, vs[1:] + [vs[0]]))

    def contains_point(self, p: Point2, *, include_boundary: bool = True) -> bool:
        """
        Ray casting point-in-polygon.
        Returns True if p is inside polygon (or on boundary if include_boundary).
        """
        x, y = float(p[0]), float(p[1])
        vs = self.vertices

        # Boundary check first (optional)
        if include_boundary:
            for a, b in self.edges():
                if _on_segment((x, y), a, b):
                    return True

        inside = False
        n = len(vs)
        for i in range(n):
            x1, y1 = vs[i]
            x2, y2 = vs[(i + 1) % n]

            # Check if the edge crosses the horizontal ray at y
            intersects = ((y1 > y) != (y2 > y))
            if intersects:
                # x coordinate of intersection of edge with horizontal line y
                x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1 + 1e-15)
                if x_int > x:
                    inside = not inside
        return inside

    def segment_intersects(self, a: Point2, b: Point2) -> bool:
        """
        True if segment ab intersects the polygon boundary OR passes through its interior.
        """
        # If either endpoint is inside, it intersects the forbidden region
        if self.contains_point(a, include_boundary=True) or self.contains_point(b, include_boundary=True):
            return True

        # Otherwise check boundary intersection
        for e1, e2 in self.edges():
            if _segments_intersect(a, b, e1, e2):
                return True
        return False

    def distance_to_boundary(self, p: Point2) -> float:
        """
        Minimum distance from point p to polygon edges.
        Useful as a "safety margin" measure.
        """
        dmin = float("inf")
        for a, b in self.edges():
            dmin = min(dmin, _dist_point_to_segment(p, a, b))
        return float(dmin)


# ============================================================
# Convenience functions for multiple fences
# ============================================================

def violates_any_fence(
    p: Point2,
    fences: Sequence[PolygonFence],
    *,
    include_boundary: bool = True,
) -> Optional[str]:
    """Return the name of the first fence containing p (or None if none)."""
    for f in fences:
        if f.contains_point(p, include_boundary=include_boundary):
            return f.name
    return None


def path_violates_any_fence(
    path_xy: Iterable[Point2],
    fences: Sequence[PolygonFence],
) -> Optional[str]:
    """
    Check a polyline path against fences.
    Returns the name of the first fence that the path enters/crosses, else None.
    """
    pts = list(path_xy)
    if len(pts) < 2:
        return None

    for f in fences:
        # Check vertices inside
        for p in pts:
            if f.contains_poin_
