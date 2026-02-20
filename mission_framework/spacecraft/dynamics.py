# mission_framework/spacecraft/dynamics.py
from __future__ import annotations
import numpy as np

MU_EARTH = 3.986004418e14   # m^3/s^2
R_EARTH  = 6378137.0        # m
J2       = 1.08262668e-3    # -

def accel_two_body(r: np.ndarray) -> np.ndarray:
    rn = np.linalg.norm(r)
    return -MU_EARTH * r / (rn**3)

def accel_j2(r: np.ndarray) -> np.ndarray:
    """
    Standard J2 acceleration in inertial frame.
    """
    x, y, z = float(r[0]), float(r[1]), float(r[2])
    r2 = x*x + y*y + z*z
    r1 = np.sqrt(r2)

    zx = z / r1
    factor = 1.5 * J2 * MU_EARTH * (R_EARTH**2) / (r1**5)

    ax = factor * x * (5.0 * zx*zx - 1.0)
    ay = factor * y * (5.0 * zx*zx - 1.0)
    az = factor * z * (5.0 * zx*zx - 3.0)
    return np.array([ax, ay, az], dtype=float)

def dynamics_eci(x: np.ndarray) -> np.ndarray:
    """
    x = [rx, ry, rz, vx, vy, vz] in meters and m/s
    """
    r = x[:3]
    v = x[3:]
    a = accel_two_body(r) + accel_j2(r)
    return np.hstack([v, a])

def rk4_step(f, x: np.ndarray, dt: float) -> np.ndarray:
    k1 = f(x)
    k2 = f(x + 0.5 * dt * k1)
    k3 = f(x + 0.5 * dt * k2)
    k4 = f(x + dt * k3)
    return x + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)