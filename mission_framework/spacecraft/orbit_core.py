# mission_framework/spacecraft/orbit_core.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from mission_framework.spacecraft.frames import julian_date_from_unix, eci_to_ecef
from mission_framework.spacecraft.dynamics import rk4_step, dynamics_eci

R_EARTH_KM = 6378.137
MU_EARTH = 3.986004418e14  # m^3/s^2


@dataclass(frozen=True)
class KeplerianElementsCore:
    """
    Strict orbital elements used internally for propagation.

    Units:
      a_m   : meters
      e     : -
      i_rad : radians
      raan_rad, argp_rad, M0_rad : radians
      epoch_unix_s : seconds since Unix epoch (UTC)
    """

    a_m: float
    e: float
    i_rad: float
    raan_rad: float
    argp_rad: float
    M0_rad: float
    epoch_unix_s: float


def keplerian_to_eci_state(el: KeplerianElementsCore) -> np.ndarray:
    """
    Convert Keplerian elements -> initial ECI Cartesian state.
    Returns x0 = [rx, ry, rz, vx, vy, vz] in meters and m/s.
    """
    a = float(el.a_m)
    e = float(el.e)
    i = float(el.i_rad)
    raan = float(el.raan_rad)
    argp = float(el.argp_rad)
    M0 = float(el.M0_rad)

    # Solve Kepler's equation: M = E - e sin E (Newton-Raphson)
    E = M0
    for _ in range(50):
        f = E - e * math.sin(E) - M0
        fp = 1.0 - e * math.cos(E)
        dE = -f / fp
        E += dE
        if abs(dE) < 1e-12:
            break

    # True anomaly from eccentric anomaly
    nu = 2.0 * math.atan2(
        math.sqrt(1.0 + e) * math.sin(E / 2.0),
        math.sqrt(1.0 - e) * math.cos(E / 2.0),
    )

    p = a * (1.0 - e * e)
    r = p / (1.0 + e * math.cos(nu))

    r_pf = np.array([r * math.cos(nu), r * math.sin(nu), 0.0], dtype=float)
    v_pf = np.array(
        [
            -math.sqrt(MU_EARTH / p) * math.sin(nu),
            math.sqrt(MU_EARTH / p) * (e + math.cos(nu)),
            0.0,
        ],
        dtype=float,
    )

    # Rotation perifocal -> ECI (3-1-3): Rz(raan) Rx(i) Rz(argp)
    co, so = math.cos(argp), math.sin(argp)
    ci, si = math.cos(i), math.sin(i)
    cr, sr = math.cos(raan), math.sin(raan)

    Q = np.array(
        [
            [cr * co - sr * so * ci, -cr * so - sr * co * ci, sr * si],
            [sr * co + cr * so * ci, -sr * so + cr * co * ci, -cr * si],
            [so * si, co * si, ci],
        ],
        dtype=float,
    )

    r_eci = Q @ r_pf
    v_eci = Q @ v_pf
    return np.hstack([r_eci, v_eci])


def propagate_eci(
    x0_eci: np.ndarray,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Strict ECI propagation using RK4 + dynamics_eci.
    Returns:
      t_rel: shape (N,)
      x_eci: shape (N,6)
    """
    x0_eci = np.asarray(x0_eci, dtype=float).reshape(6)
    if dt_s <= 0:
        raise ValueError("dt_s must be > 0.")
    if t_end_s < t_start_s:
        raise ValueError("t_end_s must be >= t_start_s.")

    n = max(2, int(math.floor((t_end_s - t_start_s) / dt_s)) + 1)
    t_rel = t_start_s + dt_s * np.arange(n, dtype=float)

    x = x0_eci.copy()
    x_hist = np.zeros((n, 6), dtype=float)

    for k in range(n):
        x_hist[k] = x
        if k < n - 1:
            x = rk4_step(dynamics_eci, x, float(dt_s))

    return t_rel, x_hist


def eci_history_to_ecef(
    epoch_unix_s: float,
    t_rel: np.ndarray,
    x_eci: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert ECI history -> ECEF history per step using JD/GMST.

    Inputs:
      epoch_unix_s: Unix epoch of t_rel=0
      t_rel: (N,)
      x_eci: (N,6)

    Returns:
      r_ecef: (N,3)
      v_ecef: (N,3)
    """
    t_rel = np.asarray(t_rel, dtype=float).reshape(-1)
    x_eci = np.asarray(x_eci, dtype=float)
    if x_eci.ndim != 2 or x_eci.shape[1] != 6:
        raise ValueError("x_eci must be shape (N,6).")
    if x_eci.shape[0] != t_rel.shape[0]:
        raise ValueError("x_eci length must match t_rel length.")

    n = t_rel.shape[0]
    r_ecef = np.zeros((n, 3), dtype=float)
    v_ecef = np.zeros((n, 3), dtype=float)

    for k in range(n):
        jd = julian_date_from_unix(float(epoch_unix_s) + float(t_rel[k]))
        re, ve = eci_to_ecef(x_eci[k, :3], x_eci[k, 3:], jd)
        r_ecef[k] = re
        v_ecef[k] = ve

    return r_ecef, v_ecef


def propagate_ecef_trajectory_from_kepler(
    el: KeplerianElementsCore,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convenience: Kepler -> x0(ECI) -> propagate ECI -> convert to ECEF (positions only).
    Returns:
      t_rel: (N,)
      r_ecef: (N,3)
    """
    x0 = keplerian_to_eci_state(el)
    t_rel, x_hist = propagate_eci(x0, t_start_s, t_end_s, dt_s)
    r_ecef, _ = eci_history_to_ecef(el.epoch_unix_s, t_rel, x_hist)
    return t_rel, r_ecef
