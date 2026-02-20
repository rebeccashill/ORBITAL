# mission_framework/aircraft/wind_model.py
"""
Wind models for aircraft simulation.

Goals:
- Provide wind as an inertial-frame velocity vector [m/s] at (x,y,z,t)
- Support time-varying and spatial variation
- Support uncertainty sampling for Monte-Carlo robustness

Coordinate convention (recommended):
- x East [m], y North [m], z Up [m] (ENU), or a consistent local tangent frame.
- Wind vector is the *air velocity of the air mass* in same frame, i.e.:
    v_ground = v_air_relative + v_wind

This module is intentionally lightweight and deterministic given a seed/rng.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

import numpy as np


class WindModel(Protocol):
    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        """Return wind vector [wx, wy, wz] in m/s at position/time."""
        ...


@dataclass(frozen=True)
class ZeroWind(WindModel):
    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        return np.zeros(3, dtype=float)


@dataclass
class UniformWind(WindModel):
    """
    Constant wind in ENU.
    Example: w_east=3 m/s, w_north=-1 m/s.
    """

    w_enu_mps: np.ndarray  # shape (3,)

    def __post_init__(self) -> None:
        self.w_enu_mps = np.asarray(self.w_enu_mps, dtype=float).reshape(3)

    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        return self.w_enu_mps.copy()


@dataclass
class SinusoidalWind(WindModel):
    """
    Smooth time-varying wind about a mean.
    Useful for "time-varying wind" requirement without external data files.
    """

    mean_enu_mps: np.ndarray  # (3,)
    amp_enu_mps: np.ndarray  # (3,)
    period_s: float = 600.0  # 10 minutes default
    phase_s: float = 0.0

    def __post_init__(self) -> None:
        self.mean_enu_mps = np.asarray(self.mean_enu_mps, dtype=float).reshape(3)
        self.amp_enu_mps = np.asarray(self.amp_enu_mps, dtype=float).reshape(3)
        if self.period_s <= 0:
            raise ValueError("period_s must be > 0")

    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        ang = 2.0 * np.pi * (t_s + self.phase_s) / self.period_s
        return self.mean_enu_mps + self.amp_enu_mps * np.sin(ang)


@dataclass
class VortexFieldWind(WindModel):
    """
    Spatially varying wind that swirls around a center (x0,y0).
    Not physically perfect, but excellent for stress-testing planners with geofences.

    w = mean + swirl_strength * [-dy, dx] / (r^2 + r0^2)
    """

    mean_enu_mps: np.ndarray  # (3,)
    center_xy_m: Tuple[float, float] = (0.0, 0.0)
    swirl_strength: float = 1500.0  # tune for difficulty
    core_radius_m: float = 250.0  # avoids singularity
    vertical_shear: float = 0.0  # optional: wz = shear * z

    def __post_init__(self) -> None:
        self.mean_enu_mps = np.asarray(self.mean_enu_mps, dtype=float).reshape(3)
        if self.core_radius_m <= 0:
            raise ValueError("core_radius_m must be > 0")

    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        x0, y0 = self.center_xy_m
        dx = x_m - x0
        dy = y_m - y0
        r2 = dx * dx + dy * dy
        denom = r2 + self.core_radius_m * self.core_radius_m

        swirl = self.swirl_strength / denom
        wx = -dy * swirl
        wy = dx * swirl
        wz = self.vertical_shear * float(z_m)

        return self.mean_enu_mps + np.array([wx, wy, wz], dtype=float)


@dataclass
class StochasticWind(WindModel):
    """
    Wraps a base wind model and adds correlated random gusts.

    - Adds a *constant per-run* bias (represents forecast error)
    - Adds a *time-correlated* gust using an OU-like discrete update

    Use one instance per simulation run with its own rng.
    """

    base: WindModel
    sigma_bias_mps: float = 1.0  # std dev of bias (per run)
    sigma_gust_mps: float = 0.8  # std dev of gust process
    tau_gust_s: float = 60.0  # correlation time
    dt_s: float = 1.0  # expected sim timestep (for stability)

    rng: Optional[np.random.Generator] = None

    # internal state
    _bias: Optional[np.ndarray] = None  # (3,)
    _gust: Optional[np.ndarray] = None  # (3,)
    _t_last: Optional[float] = None

    def reset(self, rng: Optional[np.random.Generator] = None) -> None:
        self.rng = rng if rng is not None else np.random.default_rng()
        self._bias = self.rng.normal(0.0, self.sigma_bias_mps, size=3).astype(float)
        self._gust = np.zeros(3, dtype=float)
        self._t_last = None

    def __post_init__(self) -> None:
        if self.tau_gust_s <= 0:
            raise ValueError("tau_gust_s must be > 0")
        if self.dt_s <= 0:
            raise ValueError("dt_s must be > 0")
        self.reset(self.rng)

    def _update_gust(self, t_s: float) -> None:
        if self.rng is None:
            self.rng = np.random.default_rng()
        if self._t_last is None:
            self._t_last = float(t_s)
            return
        dt = float(t_s - self._t_last)
        if dt <= 0:
            return
        self._t_last = float(t_s)

        # OU discretization
        a = np.exp(-dt / self.tau_gust_s)
        # variance of innovation so stationary variance is sigma_gust^2
        innov_std = self.sigma_gust_mps * np.sqrt(max(0.0, 1.0 - a * a))
        self._gust = a * self._gust + self.rng.normal(0.0, innov_std, size=3).astype(float)

    def wind_enu(self, x_m: float, y_m: float, z_m: float, t_s: float) -> np.ndarray:
        self._update_gust(t_s)
        w = np.asarray(self.base.wind_enu(x_m, y_m, z_m, t_s), dtype=float).reshape(3)
        return w + self._bias + self._gust
