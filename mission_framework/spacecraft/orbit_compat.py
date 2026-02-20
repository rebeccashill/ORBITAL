# mission_framework/spacecraft/orbit_compat.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from mission_framework.spacecraft.orbit_core import (
    R_EARTH_KM,
    KeplerianElementsCore,
    propagate_ecef_trajectory_from_kepler,
)

def _parse_epoch_unix(epoch_utc: str) -> Optional[float]:
    if not epoch_utc:
        return None
    try:
        from datetime import datetime, timezone
        s = epoch_utc.rstrip("Z")
        fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in s else "%Y-%m-%dT%H:%M:%S"
        dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


@dataclass(frozen=True)
class KeplerianElements:
    """
    Backwards-compatible container for mission.py YAML parsing.

    Units:
      a_km, e, i_rad, raan_rad, argp_rad, M0_rad are expected by your mission.py.
      epoch_utc is an ISO string.
    """
    a_km: float
    e: float
    i_rad: float
    raan_rad: float
    argp_rad: float
    nu_rad: float = 0.0
    M0_rad: float = 0.0
    epoch_utc: str = ""


@dataclass
class OrbitConfig:
    """
    Backwards-compatible config object for mission.py.
    """
    elements: Optional[KeplerianElements] = None
    dt_s: float = 10.0
    j2: bool = True
    drag: bool = False
    area_m2: float = 0.0
    cd: float = 2.2
    mass_kg: float = 0.0


def propagate_ecef_trajectory(
    el: KeplerianElements,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Backwards-compatible function used by mission.py.
    Returns:
      t_rel: (N,)
      r_ecef: (N,3) in meters
    """
    epoch_unix = _parse_epoch_unix(el.epoch_utc)
    if epoch_unix is None:
        epoch_unix = 0.0

    core = KeplerianElementsCore(
        a_m=float(el.a_km) * 1000.0,
        e=float(el.e),
        i_rad=float(el.i_rad),
        raan_rad=float(el.raan_rad),
        argp_rad=float(el.argp_rad),
        M0_rad=float(el.M0_rad),
        epoch_unix_s=float(epoch_unix),
    )

    return propagate_ecef_trajectory_from_kepler(core, float(t_start_s), float(t_end_s), float(dt_s))