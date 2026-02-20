# mission_framework/spacecraft/orbit.py
"""
Backwards-compatible orbit API.

- Strict core propagation lives in: orbit_core.py
- YAML/legacy compatibility lives in: orbit_compat.py

Importing from mission_framework.spacecraft.orbit keeps old callers working.
"""

from .orbit_core import R_EARTH_KM  # keep constant name stable
from .orbit_compat import KeplerianElements, OrbitConfig, propagate_ecef_trajectory

__all__ = [
    "R_EARTH_KM",
    "KeplerianElements",
    "OrbitConfig",
    "propagate_ecef_trajectory",
]
