# mission_framework/spacecraft/visibility.py
"""
Backwards-compatible visibility API.

- New strict API lives in: visibility_core.py
- Legacy adapter lives in: visibility_compat.py

Importing from mission_framework.spacecraft.visibility keeps old callers working.
"""

from .visibility_compat import compute_access_windows
from .visibility_core import R_EARTH_M, GroundSite, elevation_angle_rad, geodetic_to_ecef

__all__ = [
    "GroundSite",
    "geodetic_to_ecef",
    "elevation_angle_rad",
    "R_EARTH_M",
    "compute_access_windows",
]
