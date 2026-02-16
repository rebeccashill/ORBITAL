# mission_framework/spacecraft/visibility.py
"""
Visibility / access geometry (MODULE B / spacecraft).

Simple, consistent planning-grade model:
- Spacecraft position in ECEF (km) from orbit.py
- Spherical Earth
- Ground site ECEF from lat/lon/alt
- Visibility via elevation angle >= min_elevation_deg
- Window generation via time sampling

Units:
- lat/lon in degrees in GroundSite, converted internally to radians
- km distances, seconds times
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import math
import numpy as np

from mission_framework.spacecraft.orbit import (
    KeplerianElements,
    OrbitConfig,
    R_EARTH_KM,
    spacecraft_ecef_km,
)


# ============================================================
# Ground site / target definitions
# ============================================================

@dataclass(frozen=True)
class GroundSite:
    site_id: str
    lat_deg: float
    lon_deg: float
    alt_km: float = 0.0

    @property
    def lat_rad(self) -> float:
        return float(math.radians(float(self.lat_deg)))

    @property
    def lon_rad(self) -> float:
        return float(math.radians(float(self.lon_deg)))


def ground_ecef_km(
    lat_rad: float,
    lon_rad: float,
    alt_km: float = 0.0,
    r_earth_km: float = R_EARTH_KM,
) -> np.ndarray:
    """
    Spherical Earth conversion (ECEF):
      r = (R + alt) [cos lat cos lon, cos lat sin lon, sin lat]
    """
    R = float(r_earth_km) + float(alt_km)
    clat = math.cos(float(lat_rad))
    slat = math.sin(float(lat_rad))
    clon = math.cos(float(lon_rad))
    slon = math.sin(float(lon_rad))
    return np.array([R * clat * clon, R * clat * slon, R * slat], dtype=float)


# ============================================================
# Visibility math
# ============================================================

def elevation_angle_rad(r_site_ecef: np.ndarray, r_sc_ecef: np.ndarray) -> float:
    """
    Elevation at ground site to spacecraft.

    up_hat ~ normalized site radius vector
    los_hat = (r_sc - r_site) / ||r_sc - r_site||
    elevation = asin( dot(los_hat, up_hat) )
    """
    r_site = np.asarray(r_site_ecef, dtype=float).reshape(3)
    r_sc = np.asarray(r_sc_ecef, dtype=float).reshape(3)

    los = r_sc - r_site
    los_norm = float(np.linalg.norm(los))
    if los_norm < 1e-12:
        return float(math.pi / 2.0)

    los_hat = los / los_norm
    up_norm = float(np.linalg.norm(r_site))
    if up_norm < 1e-12:
        return float(-math.pi / 2.0)
    up_hat = r_site / up_norm

    s = float(np.clip(np.dot(los_hat, up_hat), -1.0, 1.0))
    return float(math.asin(s))


def is_visible(
    el: KeplerianElements,
    site: GroundSite,
    t_s: float,
    *,
    cfg: Optional[OrbitConfig] = None,
    min_elevation_deg: float = 10.0,
    max_range_km: Optional[float] = None,
) -> bool:
    """
    True if spacecraft elevation >= min_elevation_deg at time t.
    Optionally enforce a max slant range.
    """
    cfg = cfg or OrbitConfig()

    r_sc = spacecraft_ecef_km(el, float(t_s), cfg=cfg)
    r_site = ground_ecef_km(site.lat_rad, site.lon_rad, site.alt_km, r_earth_km=cfg.r_earth_km)

    elev = elevation_angle_rad(r_site, r_sc)
    if elev < math.radians(float(min_elevation_deg)):
        return False

    if max_range_km is not None:
        rng_km = float(np.linalg.norm(r_sc - r_site))
        if rng_km > float(max_range_km):
            return False

    return True


# ============================================================
# Window generation
# ============================================================

@dataclass(frozen=True)
class AccessWindow:
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return float(self.end_s - self.start_s)

def compute_access_windows(
    el: KeplerianElements,
    site: GroundSite,
    *,
    t_start_s: Optional[float],
    t_end_s: Optional[float],
    step_s: float = 30.0,
    cfg: Optional[OrbitConfig] = None,
    min_elevation_deg: float = 10.0,
    max_range_km: Optional[float] = None,
    merge_gap_s: float = 120.0,
) -> List[AccessWindow]:
    cfg = cfg or OrbitConfig()

    if t_start_s is None or t_end_s is None:
        raise ValueError("compute_access_windows requires t_start_s and t_end_s (got None).")

    t0 = float(t_start_s)
    t1 = float(t_end_s)
    dt = float(step_s)
    if dt <= 0:
        raise ValueError("step_s must be > 0")
    if t1 <= t0:
        return []

    times = np.arange(t0, t1 + 1e-9, dt, dtype=float)

    def vis(t: float) -> bool:
        return is_visible(
            el,
            site,
            t,
            cfg=cfg,
            min_elevation_deg=min_elevation_deg,
            max_range_km=max_range_km,
        )

    flags = [vis(float(t)) for t in times]

    windows: List[AccessWindow] = []
    in_win = False
    start: Optional[float] = None

    for i, t in enumerate(times):
        if flags[i] and not in_win:
            in_win = True
            start = float(t)
        elif (not flags[i]) and in_win:
            in_win = False
            end = float(t)
            if start is not None:
                windows.append(AccessWindow(start_s=float(start), end_s=end))
            start = None

    if in_win and start is not None:
        windows.append(AccessWindow(start_s=float(start), end_s=float(times[-1])))

    if not windows:
        return []

    # Merge gaps
    merged: List[AccessWindow] = [windows[0]]
    for w in windows[1:]:
        prev = merged[-1]
        if float(w.start_s - prev.end_s) <= float(merge_gap_s):
            merged[-1] = AccessWindow(start_s=prev.start_s, end_s=max(prev.end_s, w.end_s))
        else:
            merged.append(w)

    return merged


def compute_multi_site_windows(
    el: KeplerianElements,
    sites: Sequence[GroundSite],
    *,
    t_start_s: Optional[float],
    t_end_s: Optional[float],
    step_s: float = 30.0,
    cfg: Optional[OrbitConfig] = None,
    min_elevation_deg: float = 10.0,
    max_range_km: Optional[float] = None,
) -> List[Tuple[str, List[AccessWindow]]]:
    cfg = cfg or OrbitConfig()

    if t_start_s is None or t_end_s is None:
        raise ValueError("compute_multi_site_windows requires t_start_s and t_end_s (got None).")

    out: List[Tuple[str, List[AccessWindow]]] = []
    for s in sites:
        wins = compute_access_windows(
            el,
            s,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            step_s=step_s,
            cfg=cfg,
            min_elevation_deg=min_elevation_deg,
            max_range_km=max_range_km,
        )
        out.append((s.site_id, wins))
    return out
