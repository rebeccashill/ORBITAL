# mission_framework/spacecraft/frames.py
from __future__ import annotations
import numpy as np

W_EARTH = 7.2921150e-5  # rad/s

def julian_date_from_unix(t_unix_s: float) -> float:
    # Unix epoch -> Julian Date (UTC as proxy for UT1; fine for LEO planning)
    return 2440587.5 + float(t_unix_s) / 86400.0

def gmst_iau82_rad(jd_ut1: float) -> float:
    """
    IAU 1982 GMST approximation.
    Returns radians in [0, 2pi).
    """
    T = (float(jd_ut1) - 2451545.0) / 36525.0
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * T
        + 0.093104 * T**2
        - 6.2e-6 * T**3
    )
    gmst_sec = gmst_sec % 86400.0
    return gmst_sec * (2.0 * np.pi / 86400.0)

def R3(theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[ c,  s, 0.0],
                     [-s,  c, 0.0],
                     [0.0, 0.0, 1.0]])

def eci_to_ecef(r_eci: np.ndarray, v_eci: np.ndarray, jd_ut1: float):
    """
    ECI -> ECEF with proper velocity frame correction:
      r_ecef = R3(gmst) r_eci
      v_ecef = R3(gmst) v_eci - ω×r_ecef
    """
    theta = gmst_iau82_rad(jd_ut1)
    R = R3(theta)
    r_ecef = R @ r_eci
    v_rot  = R @ v_eci
    omega  = np.array([0.0, 0.0, W_EARTH])
    v_ecef = v_rot - np.cross(omega, r_ecef)
    return r_ecef, v_ecef

def ecef_to_eci(r_ecef: np.ndarray, v_ecef: np.ndarray, jd_ut1: float):
    theta = gmst_iau82_rad(jd_ut1)
    R = R3(theta)
    Rt = R.T
    omega = np.array([0.0, 0.0, W_EARTH])
    r_eci = Rt @ r_ecef
    v_eci = Rt @ (v_ecef + np.cross(omega, r_ecef))
    return r_eci, v_eci