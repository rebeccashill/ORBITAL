# mission_framework/aircraft/wind.py
"""
Time/space varying wind model (MODULE A / aircraft).

Provides wind field generators compatible with aircraft.model.PointMassUAV:

    wind_fn(t, x, y, z) -> (wx, wy, wz)   [m/s] in world frame

Conventions:
- x, y: horizontal position [m]
- z: altitude [m] (positive up)
- wx, wy, wz: wind velocity components [m/s] in world frame
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import math
import random


WindFn = Callable[[float, float, float, float], Tuple[float, float, float]]


# ============================================================
# Deterministic wind fields
# ============================================================

def zero_wind() -> WindFn:
    """No wind everywhere."""
    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        return 0.0, 0.0, 0.0
    return _fn


def constant_wind(wx: float = 0.0, wy: float = 0.0, wz: float = 0.0) -> WindFn:
    """Constant wind vector everywhere."""
    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        return float(wx), float(wy), float(wz)
    return _fn


def uniform_from_speed_dir(
    speed: float,
    direction_deg: float,
    *,
    wz: float = 0.0,
) -> WindFn:
    """
    Constant horizontal wind specified by speed and direction.

    direction_deg is the direction the wind is *blowing toward* in world frame.
    """
    theta = math.radians(direction_deg)
    wx = float(speed) * math.cos(theta)
    wy = float(speed) * math.sin(theta)
    return constant_wind(wx, wy, wz)


def linear_shear(
    base_wx: float = 0.0,
    base_wy: float = 0.0,
    shear_wx_per_m: float = 0.0,
    shear_wy_per_m: float = 0.0,
    *,
    z_ref: float = 0.0,
    wz: float = 0.0,
) -> WindFn:
    """
    Linear wind shear with altitude:
        wx(z) = base_wx + shear_wx_per_m * (z - z_ref)
        wy(z) = base_wy + shear_wy_per_m * (z - z_ref)
    """
    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        dz = float(z - z_ref)
        wx = float(base_wx + shear_wx_per_m * dz)
        wy = float(base_wy + shear_wy_per_m * dz)
        return wx, wy, float(wz)
    return _fn


def sinusoidal_gust(
    mean_wx: float = 0.0,
    mean_wy: float = 0.0,
    amp_wx: float = 2.0,
    amp_wy: float = 2.0,
    *,
    period_s: float = 30.0,
    phase_s: float = 0.0,
    wz: float = 0.0,
) -> WindFn:
    """
    Time-varying sinusoidal gust about a mean wind:
        wx(t) = mean_wx + amp_wx * sin(2π (t+phase)/period)
        wy(t) = mean_wy + amp_wy * sin(2π (t+phase)/period)
    """
    w = 2.0 * math.pi / max(float(period_s), 1e-9)

    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        s = math.sin(w * (float(t) + float(phase_s)))
        wx = float(mean_wx + amp_wx * s)
        wy = float(mean_wy + amp_wy * s)
        return wx, wy, float(wz)

    return _fn


# ============================================================
# Stochastic turbulence (stateful callable)
# ============================================================

@dataclass(frozen=True)
class TurbulenceParams:
    """
    Mean wind + correlated turbulence.

    sigma: std dev of gust components [m/s]
    tau_s: correlation time constant [s]
    seed: RNG seed for reproducibility
    """
    sigma: float = 1.0
    tau_s: float = 10.0
    seed: Optional[int] = 0


def turbulent_wind(
    mean_wx: float = 0.0,
    mean_wy: float = 0.0,
    mean_wz: float = 0.0,
    *,
    params: TurbulenceParams = TurbulenceParams(),
) -> WindFn:
    """
    Mean wind plus simple OU-like correlated turbulence.

    NOTE: This wind_fn has internal state (closure), so it should be used
    for a single simulation rollout. For reproducibility, set params.seed.
    """
    rng = random.Random(params.seed)

    gx = 0.0
    gy = 0.0
    gz = 0.0
    t_prev: Optional[float] = None

    sigma = float(params.sigma)
    tau = max(float(params.tau_s), 1e-6)

    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        nonlocal gx, gy, gz, t_prev

        t = float(t)
        if t_prev is None:
            dt = 0.0
        else:
            dt = max(0.0, t - float(t_prev))
        t_prev = t

        if dt > 0.0:
            a = math.exp(-dt / tau)
            b = math.sqrt(max(0.0, 1.0 - a * a))

            gx = a * gx + b * sigma * rng.gauss(0.0, 1.0)
            gy = a * gy + b * sigma * rng.gauss(0.0, 1.0)
            gz = a * gz + b * sigma * rng.gauss(0.0, 1.0)

        return (
            float(mean_wx + gx),
            float(mean_wy + gy),
            float(mean_wz + gz),
        )

    return _fn


# ============================================================
# Composition utilities
# ============================================================

def add_wind(a: WindFn, b: WindFn) -> WindFn:
    """Sum two wind fields."""
    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        ax, ay, az = a(t, x, y, z)
        bx, by, bz = b(t, x, y, z)
        return float(ax + bx), float(ay + by), float(az + bz)
    return _fn


def scale_wind(w: WindFn, k: float) -> WindFn:
    """Scale a wind field by k."""
    k = float(k)
    def _fn(t: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        wx, wy, wz = w(t, x, y, z)
        return float(k * wx), float(k * wy), float(k * wz)
    return _fn
