# mission_framework/aircraft/mission.py
"""
Waypoint mission definition (MODULE A / aircraft).

This module defines:
- Waypoints (position + optional speed/altitude/loiter constraints)
- Missions (ordered list of waypoints + metadata)
- Convenience utilities (distance, interpolation, basic progress checks)

Coordinates:
- Uses a flat-earth planar frame: x,y in meters; z in meters (altitude, positive up).
- If you have lat/lon, project to local ENU before creating waypoints.

This stays "planner-friendly":
- The mission is purely declarative (no simulation performed here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import math


# ============================================================
# Helpers
# ============================================================

def _dist3(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


# ============================================================
# Waypoints / Missions
# ============================================================

@dataclass(frozen=True)
class Waypoint:
    """
    A mission waypoint.

    Required:
      x, y, z: target location [m]

    Optional "hints"/constraints:
      radius_m:      capture radius for considering it reached
      target_speed:  desired speed near waypoint [m/s]
      min_speed/max_speed: allowable speed near waypoint [m/s]
      min_alt/max_alt: allowable altitude near waypoint [m]
      loiter_time_s: time to loiter after reaching waypoint [s]
      name:          identifier
      tags:          free-form metadata (e.g., "inspect", "drop", "handoff")
    """
    x: float
    y: float
    z: float = 0.0

    radius_m: float = 10.0

    target_speed: Optional[float] = None
    min_speed: Optional[float] = None
    max_speed: Optional[float] = None

    min_alt: Optional[float] = None
    max_alt: Optional[float] = None

    loiter_time_s: float = 0.0

    name: str = ""
    tags: Dict[str, object] = field(default_factory=dict)

    def pos3(self) -> Tuple[float, float, float]:
        return float(self.x), float(self.y), float(self.z)

    def pos2(self) -> Tuple[float, float]:
        return float(self.x), float(self.y)


@dataclass(frozen=True)
class Mission:
    """
    An ordered list of waypoints.

    mission_id: unique identifier
    waypoints: ordered list
    metadata: free-form mission metadata (client, payload, etc.)
    """
    waypoints: Tuple[Waypoint, ...]
    mission_id: str =_
