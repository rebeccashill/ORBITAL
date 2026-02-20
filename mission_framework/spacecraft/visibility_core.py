# mission_framework/spacecraft/visibility_core.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np

R_EARTH_M = 6378137.0  # spherical Earth proxy (m)


# -------------------------
# Geometry helpers
# -------------------------


def geodetic_to_ecef(lat_rad: float, lon_rad: float, alt_m: float) -> np.ndarray:
    clat, slat = np.cos(lat_rad), np.sin(lat_rad)
    clon, slon = np.cos(lon_rad), np.sin(lon_rad)
    r = R_EARTH_M + float(alt_m)
    return np.array([r * clat * clon, r * clat * slon, r * slat], dtype=float)


def elevation_angle_rad(r_sat_ecef: np.ndarray, r_gs_ecef: np.ndarray) -> float:
    """Geometric elevation angle (rad) using zenith proxy at ground site."""
    rho = r_sat_ecef - r_gs_ecef
    rho_norm = np.linalg.norm(rho)
    if rho_norm <= 0.0:
        return -np.inf
    rho_hat = rho / rho_norm

    z_norm = np.linalg.norm(r_gs_ecef)
    if z_norm <= 0.0:
        return -np.inf
    zenith_hat = r_gs_ecef / z_norm

    # arcsin(dot(rho_hat, zenith_hat)) is a common quick proxy for elevation
    return float(np.arcsin(np.clip(np.dot(rho_hat, zenith_hat), -1.0, 1.0)))


# -------------------------
# Typed domain objects
# -------------------------


@dataclass(frozen=True)
class GroundSite:
    """
    Typed ground site definition used by access-window computation.

    Canonical altitude is meters.
    """

    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0
    min_elev_deg: float = 10.0
    site_id: Optional[str] = None

    @classmethod
    def from_km(
        cls,
        *,
        site_id: Optional[str],
        lat_deg: float,
        lon_deg: float,
        alt_km: float = 0.0,
        min_elev_deg: float = 10.0,
        name: str = "",
    ) -> "GroundSite":
        nm = name.strip() or (site_id or "GS")
        return cls(
            name=nm,
            lat_deg=float(lat_deg),
            lon_deg=float(lon_deg),
            alt_m=float(alt_km) * 1000.0,
            min_elev_deg=float(min_elev_deg),
            site_id=site_id,
        )

    def ecef(self) -> np.ndarray:
        return geodetic_to_ecef(
            np.deg2rad(float(self.lat_deg)),
            np.deg2rad(float(self.lon_deg)),
            float(self.alt_m),
        )

    @property
    def min_elev_rad(self) -> float:
        return float(np.deg2rad(float(self.min_elev_deg)))


# -------------------------
# Strict, typed API
# -------------------------


def compute_access_windows(
    t: np.ndarray,
    r_ecef: np.ndarray,
    sites: List[GroundSite],
) -> Dict[str, List[Tuple[float, float]]]:
    """
    Compute ground-station access windows.

    Strict requirements:
      - t: shape (T,)
      - r_ecef: shape (T,3), same T as t
      - sites: list[GroundSite]

    Returns:
      dict[site_name -> list of (t_start, t_end)]
    """
    t = np.asarray(t, dtype=float).reshape(-1)
    r_ecef = np.asarray(r_ecef, dtype=float)

    if t.size < 2:
        raise ValueError("t must contain at least 2 time points.")
    if r_ecef.ndim != 2 or r_ecef.shape[1] != 3:
        raise ValueError("r_ecef must be shape (T,3).")
    if r_ecef.shape[0] != t.shape[0]:
        raise ValueError("r_ecef must have the same length as t.")
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(r_ecef)):
        raise ValueError("t and r_ecef must be finite.")
    if np.any(np.diff(t) < -1e-12):
        raise ValueError("t must be non-decreasing.")

    out: Dict[str, List[Tuple[float, float]]] = {}

    for site in sites:
        name = str(site.name)
        r_gs = site.ecef()
        min_el = site.min_elev_rad

        # boolean visibility mask
        mask = np.zeros(t.shape[0], dtype=bool)
        for k in range(t.shape[0]):
            mask[k] = elevation_angle_rad(r_ecef[k], r_gs) >= min_el

        # convert mask -> contiguous windows
        windows: List[Tuple[float, float]] = []
        in_win = False
        t0 = 0.0

        for k in range(t.shape[0]):
            if mask[k] and not in_win:
                in_win = True
                t0 = float(t[k])
            elif in_win and (not mask[k]):
                t1 = float(t[k])
                if t1 > t0:
                    windows.append((t0, t1))
                in_win = False

        if in_win:
            t1 = float(t[-1])
            if t1 > t0:
                windows.append((t0, t1))

        out[name] = windows

    return out
