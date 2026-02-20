# mission_framework/spacecraft/propagator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from mission_framework.spacecraft.dynamics import DynamicsConfig, dynamics_eci, rk4_step
from mission_framework.spacecraft.frames import eci_to_ecef, julian_date_from_unix


@dataclass(frozen=True)
class PropagatorConfig:
    dt_s: float = 10.0
    dynamics: DynamicsConfig = DynamicsConfig()


class Propagator:
    """
    Simple spacecraft propagator:
      - propagates inertial state in ECI with RK4
      - converts to ECEF per step using GMST

    State:
      x = [rx, ry, rz, vx, vy, vz] in meters and m/s
    """

    def __init__(self, cfg: PropagatorConfig = PropagatorConfig()):
        if cfg.dt_s <= 0:
            raise ValueError("PropagatorConfig.dt_s must be > 0.")
        self.cfg = cfg

    def propagate_eci(
        self,
        x0_eci: np.ndarray,
        t_start_s: float,
        t_end_s: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns:
          t_rel: (N,)
          x_eci: (N,6)
        """
        x0 = np.asarray(x0_eci, dtype=float).reshape(6)
        t0 = float(t_start_s)
        t1 = float(t_end_s)
        dt = float(self.cfg.dt_s)

        if t1 < t0:
            raise ValueError("t_end_s must be >= t_start_s.")

        n = max(2, int(np.floor((t1 - t0) / dt)) + 1)
        t_rel = t0 + dt * np.arange(n, dtype=float)

        x = x0.copy()
        x_hist = np.zeros((n, 6), dtype=float)

        # dynamics function with config captured
        def f(xx: np.ndarray) -> np.ndarray:
            return dynamics_eci(xx, cfg=self.cfg.dynamics)

        for k in range(n):
            x_hist[k] = x
            if k < n - 1:
                x = rk4_step(f, x, dt)

        return t_rel, x_hist

    def to_ecef(
        self,
        epoch_unix_s: float,
        t_rel: np.ndarray,
        x_eci: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert ECI history to ECEF history using GMST per time step.
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

        epoch = float(epoch_unix_s)
        for k in range(n):
            jd = julian_date_from_unix(epoch + float(t_rel[k]))
            re, ve = eci_to_ecef(x_eci[k, :3], x_eci[k, 3:], jd)
            r_ecef[k] = re
            v_ecef[k] = ve

        return r_ecef, v_ecef

    def propagate_ecef(
        self,
        x0_eci: np.ndarray,
        epoch_unix_s: float,
        t_start_s: float,
        t_end_s: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Convenience: propagate ECI then convert to ECEF.
        Returns:
          t_rel: (N,)
          x_eci: (N,6)
          r_ecef: (N,3)
        """
        t_rel, x_eci = self.propagate_eci(x0_eci, t_start_s, t_end_s)
        r_ecef, _ = self.to_ecef(epoch_unix_s, t_rel, x_eci)
        return t_rel, x_eci, r_ecef
