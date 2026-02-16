# mission_framework/spacecraft/orbit.py
"""
Spacecraft orbit utilities (MODULE B).

Goal: "usable level" orbit/visibility support for CubeSat-style LEO ops.

We implement a simplified, consistent model:
- Two-body Kepler propagation for a Keplerian orbit (a, e, i, RAAN, argp, M0)
- Convert to ECI position (km) at time t
- Convert ECI -> ECEF with a simple Earth rotation model
- Convert ECEF -> geodetic lat/lon/alt (spherical Earth approximation by default)

This is intentionally lightweight (no heavy deps) and good enough for:
- Ground target visibility checks
- Ground station contact windows
- Planning/scheduling feasibility

Units:
- Distances are in kilometers unless stated otherwise.
- Angles are in radians unless stated otherwise.
- Times are in seconds.

If you later want more fidelity, you can swap in SGP4, Vallado routines, etc.,
without changing the high-level framework interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import math
import numpy as np


# ============================================================
# Constants (can be overridden if needed)
# ============================================================

MU_EARTH_KM3_S2 = 398600.4418          # Earth's gravitational parameter
R_EARTH_KM = 6378.137                 # WGS-84 equatorial radius (km)
OMEGA_EARTH_RAD_S = 7.2921150e-5      # Earth rotation rate (rad/s)


# ============================================================
# Basic vector helpers
# ============================================================

def _rot_z(theta: float) -> np.ndarray:
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([[c, -s, 0.0],
                     [s,  c, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def _rot_x(theta: float) -> np.ndarray:
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([[1.0, 0.0, 0.0],
                     [0.0,  c, -s],
                     [0.0,  s,  c]], dtype=float)


# ============================================================
# Kepler / anomaly utilities
# ============================================================

def mean_motion_rad_s(a_km: float, mu_km3_s2: float = MU_EARTH_KM3_S2) -> float:
    """Mean motion n = sqrt(mu/a^3)."""
    a = float(a_km)
    return math.sqrt(mu_km3_s2 / (a ** 3))


def solve_kepler_E(M: float, e: float, tol: float = 1e-10, max_iter: int = 50) -> float:
    """
    Solve Kepler's equation for eccentric anomaly E:
        M = E - e*sin(E)
    for 0<=e<1.

    Uses Newton-Raphson with a safe initial guess.
    """
    e = float(e)
    M = float(M)

    # Normalize M to [-pi, pi] for numerical stability
    M = (M + math.pi) % (2.0 * math.pi) - math.pi

    if e < 1e-8:
        return M

    # Initial guess
    E = M if e < 0.8 else math.pi * (1.0 if M >= 0 else -1.0)

    for _ in range(max_iter):
        f = E - e * math.sin(E) - M
        fp = 1.0 - e * math.cos(E)
        dE = -f / fp
        E += dE
        if abs(dE) < tol:
            break
    return float(E)


def true_anomaly_from_E(E: float, e: float) -> float:
    """Convert eccentric anomaly to true anomaly."""
    e = float(e)
    c = math.cos(E)
    s = math.sin(E)
    denom = 1.0 - e * c
    # tan(nu/2) = sqrt((1+e)/(1-e)) * tan(E/2)
    nu = math.atan2(math.sqrt(1.0 - e * e) * s, c - e)
    return float(nu)


# ============================================================
# Orbit definition + propagation
# ============================================================

@dataclass(frozen=True)
class KeplerianElements:
    """
    Standard Keplerian elements at an epoch.
    """
    a_km: float
    e: float
    i_rad: float
    raan_rad: float
    argp_rad: float
    M0_rad: float
    epoch_utc: str = "2026-01-01T00:00:00Z"  # used mainly as metadata


@dataclass(frozen=True)
class OrbitConfig:
    """
    Orbit propagation config.
    """
    mu_km3_s2: float = MU_EARTH_KM3_S2
    r_earth_km: float = R_EARTH_KM
    omega_earth_rad_s: float = OMEGA_EARTH_RAD_S
    spherical_earth: bool = True  # for lat/lon conversion


def perifocal_position_km(a_km: float, e: float, nu: float) -> np.ndarray:
    """
    Position in the perifocal (PQW) frame for a Keplerian orbit.
    """
    a = float(a_km)
    e = float(e)
    nu = float(nu)
    p = a * (1.0 - e * e)
    r = p / (1.0 + e * math.cos(nu))
    return np.array([r * math.cos(nu), r * math.sin(nu), 0.0], dtype=float)


def pqw_to_eci_matrix(i_rad: float, raan_rad: float, argp_rad: float) -> np.ndarray:
    """
    Rotation matrix from PQW (perifocal) to ECI:
        R = Rz(RAAN) * Rx(i) * Rz(argp)
    """
    return _rot_z(raan_rad) @ _rot_x(i_rad) @ _rot_z(argp_rad)


def propagate_eci_km(el: KeplerianElements, t_s: float, cfg: OrbitConfig = OrbitConfig()) -> np.ndarray:
    """
    Propagate orbit to time t (seconds since epoch) and return ECI position (km).
    Two-body Kepler propagation.

    Note: This ignores J2, drag, etc. (acceptable for simplified planning).
    """
    a = float(el.a_km)
    e = float(el.e)
    n = mean_motion_rad_s(a, cfg.mu_km3_s2)

    M = float(el.M0_rad + n * float(t_s))
    E = solve_kepler_E(M, e)
    nu = true_anomaly_from_E(E, e)

    r_pqw = perifocal_position_km(a, e, nu)
    R = pqw_to_eci_matrix(el.i_rad, el.raan_rad, el.argp_rad)
    r_eci = R @ r_pqw
    return r_eci.astype(float)


def eci_to_ecef_km(r_eci_km: np.ndarray, t_s: float, cfg: OrbitConfig = OrbitConfig()) -> np.ndarray:
    """
    Convert ECI -> ECEF using a simple Earth rotation about Z:
        r_ecef = Rz(-omega*t) * r_eci
    """
    theta = float(cfg.omega_earth_rad_s * float(t_s))
    return (_rot_z(-theta) @ np.asarray(r_eci_km, dtype=float)).astype(float)


# ============================================================
# ECEF <-> lat/lon (simple)
# ============================================================

def ecef_to_latlonalt_spherical(r_ecef_km: np.ndarray, r_earth_km: float = R_EARTH_KM) -> Tuple[float, float, float]:
    """
    Spherical Earth approximation:
      lat = atan2(z, sqrt(x^2+y^2))
      lon = atan2(y, x)
      alt = ||r|| - R
    Returns (lat_rad, lon_rad, alt_km).
    """
    x, y, z = map(float, np.asarray(r_ecef_km, dtype=float).reshape(3))
    rho = math.hypot(x, y)
    lat = math.atan2(z, rho)
    lon = math.atan2(y, x)
    r = math.sqrt(x * x + y * y + z * z)
    alt = r - float(r_earth_km)
    return float(lat), float(lon), float(alt)


def ecef_to_latlonalt(r_ecef_km: np.ndarray, cfg: OrbitConfig = OrbitConfig()) -> Tuple[float, float, float]:
    """
    Convert ECEF to geodetic-ish lat/lon/alt.

    Currently uses spherical model by default (good enough for planning demos).
    """
    return ecef_to_latlonalt_spherical(r_ecef_km, r_earth_km=cfg.r_earth_km)


# ============================================================
# Convenience end-to-end helpers
# ============================================================

def spacecraft_subpoint_latlon(el: KeplerianElements, t_s: float, cfg: OrbitConfig = OrbitConfig()) -> Tuple[float, float]:
    """
    Return spacecraft subpoint (lat, lon) in radians at time t.
    """
    r_eci = propagate_eci_km(el, t_s, cfg=cfg)
    r_ecef = eci_to_ecef_km(r_eci, t_s, cfg=cfg)
    lat, lon, _alt = ecef_to_latlonalt(r_ecef, cfg=cfg)
    return float(lat), float(lon)


def spacecraft_ecef_km(el: KeplerianElements, t_s: float, cfg: OrbitConfig = OrbitConfig()) -> np.ndarray:
    """ECI->ECEF at time t."""
    r_eci = propagate_eci_km(el, t_s, cfg=cfg)
    return eci_to_ecef_km(r_eci, t_s, cfg=cfg)