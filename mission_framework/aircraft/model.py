# mission_framework/aircraft/model.py
"""
Point-mass UAV dynamics (MODULE A / aircraft).

Lightweight point-mass kinematics suitable for optimization loops.

State (world frame, z-up):
    x, y, z   [m]
    psi       heading/yaw [rad]
    v         airspeed magnitude [m/s]

Control:
    v_cmd         desired airspeed [m/s]
    psi_rate_cmd  desired heading rate [rad/s]
    vz_cmd        desired vertical speed [m/s] (optional)

Wind:
    wind_fn(t, x, y, z) -> (wx, wy, wz) [m/s] world-frame wind velocity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import math


# ============================================================
# Helpers
# ============================================================

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def wrap_angle_pi(a: float) -> float:
    """Wrap angle to (-pi, pi]."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


# Wind model signature: returns (wx, wy, wz) in world frame [m/s]
WindFn = Callable[[float, float, float, float], Tuple[float, float, float]]


# ============================================================
# Data structures
# ============================================================

@dataclass(frozen=True)
class AircraftParams:
    # Speed limits
    v_min: float = 10.0
    v_max: float = 40.0

    # Longitudinal accel limits (simple “track v_cmd with bounded accel”)
    a_long_max: float = 2.0     # [m/s^2]
    a_long_min: float = -3.0    # [m/s^2] (decel)

    # Heading rate limits
    psi_rate_max: float = math.radians(25.0)  # [rad/s]
    psi_rate_min: float = -math.radians(25.0)

    # Vertical speed limits (z-up positive)
    vz_max: float = 5.0
    vz_min: float = -5.0

    # Optional: enforce a minimum turn radius R by bounding |psi_rate| <= v/R
    min_turn_radius: Optional[float] = None  # [m]

    # Numerics
    dt_default: float = 1.0


@dataclass
class AircraftState:
    x: float
    y: float
    z: float
    psi: float   # heading [rad]
    v: float     # airspeed [m/s]

    def copy(self) -> "AircraftState":
        return AircraftState(self.x, self.y, self.z, self.psi, self.v)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": float(self.x),
            "y": float(self.y),
            "z": float(self.z),
            "psi": float(self.psi),
            "v": float(self.v),
        }


@dataclass(frozen=True)
class AircraftControl:
    v_cmd: float
    psi_rate_cmd: float
    vz_cmd: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "v_cmd": float(self.v_cmd),
            "psi_rate_cmd": float(self.psi_rate_cmd),
            "vz_cmd": float(self.vz_cmd),
        }


# ============================================================
# Dynamics
# ============================================================

class PointMassUAV:
    """
    Point-mass kinematic UAV with simple accel/rate limits.

    Methods:
        step(state, control, t, dt, wind_fn) -> next_state
        propagate(initial, controls, ...) -> (states, times)
    """

    def __init__(self, params: Optional[AircraftParams] = None):
        self.p = params if params is not None else AircraftParams()

    def _limit_heading_rate(self, v: float, psi_rate_cmd: float) -> float:
        psi_rate = clamp(psi_rate_cmd, self.p.psi_rate_min, self.p.psi_rate_max)

        if self.p.min_turn_radius is not None and self.p.min_turn_radius > 0:
            max_rate = abs(v) / float(self.p.min_turn_radius)
            psi_rate = clamp(psi_rate, -max_rate, max_rate)

        return psi_rate

    def _speed_update(self, v: float, v_cmd: float, dt: float) -> float:
        v_cmd = clamp(v_cmd, self.p.v_min, self.p.v_max)
        dv = v_cmd - v

        a_des = dv / dt if dt > 0 else 0.0
        a = clamp(a_des, self.p.a_long_min, self.p.a_long_max)

        v_new = v + a * dt
        return clamp(v_new, self.p.v_min, self.p.v_max)

    def _vz_update(self, vz_cmd: float) -> float:
        return clamp(vz_cmd, self.p.vz_min, self.p.vz_max)

    def step(
        self,
        state: AircraftState,
        control: AircraftControl,
        *,
        t: float,
        dt: Optional[float] = None,
        wind_fn: Optional[WindFn] = None,
    ) -> AircraftState:
        """
        One Euler integration step.

        Ground velocity = air-relative velocity + wind.
        """
        if dt is None:
            dt = self.p.dt_default
        if dt <= 0:
            return state.copy()

        # Update airspeed and heading
        v_new = self._speed_update(state.v, control.v_cmd, dt)
        psi_rate = self._limit_heading_rate(v_new, control.psi_rate_cmd)
        psi_new = wrap_angle_pi(state.psi + psi_rate * dt)

        # Vertical speed
        vz_air = self._vz_update(control.vz_cmd)

        # Air-relative velocity in world frame
        vx_air = v_new * math.cos(psi_new)
        vy_air = v_new * math.sin(psi_new)

        # Wind in world frame
        if wind_fn is None:
            wx = wy = wz = 0.0
        else:
            wx, wy, wz = wind_fn(float(t), state.x, state.y, state.z)

        # Ground-relative velocity
        vx = vx_air + wx
        vy = vy_air + wy
        vz = vz_air + wz

        # Integrate
        x_new = state.x + vx * dt
        y_new = state.y + vy * dt
        z_new = state.z + vz * dt

        return AircraftState(x=x_new, y=y_new, z=z_new, psi=psi_new, v=v_new)

    def propagate(
        self,
        initial: AircraftState,
        controls: List[AircraftControl],
        *,
        t0: float = 0.0,
        dt: Optional[float] = None,
        wind_fn: Optional[WindFn] = None,
        include_initial: bool = True,
    ) -> Tuple[List[AircraftState], List[float]]:
        """
        Propagate over a list of controls, each applied for one dt.

        Returns:
            states: list of AircraftState
            times:  list of times aligned with states
        """
        if dt is None:
            dt = self.p.dt_default

        states: List[AircraftState] = []
        times: List[float] = []

        s = initial.copy()
        t = float(t0)

        if include_initial:
            states.append(s.copy())
            times.append(t)

        for u in controls:
            s = self.step(s, u, t=t, dt=dt, wind_fn=wind_fn)
            t += dt
            states.append(s.copy())
            times.append(t)

        return states, times


# ============================================================
# Convenience helpers
# ============================================================

def default_state(
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    psi_deg: float = 0.0,
    v: float = 20.0,
) -> AircraftState:
    return AircraftState(x=x, y=y, z=z, psi=math.radians(psi_deg), v=v)


def control_from_heading(
    *,
    v_cmd: float,
    psi_cmd: float,
    psi_current: float,
    dt: float,
    psi_rate_limit: float,
    vz_cmd: float = 0.0,
) -> AircraftControl:
    """
    Helper if planner outputs desired heading (psi_cmd) rather than heading-rate.
    Converts heading error into a bounded psi_rate_cmd.
    """
    dpsi = wrap_angle_pi(float(psi_cmd) - float(psi_current))
    psi_rate_cmd = clamp(dpsi / max(dt, 1e-9), -abs(psi_rate_limit), abs(psi_rate_limit))
    return AircraftControl(v_cmd=float(v_cmd), psi_rate_cmd=float(psi_rate_cmd), vz_cmd=float(vz_cmd))
