# mission_framework/aircraft/dynamics.py
"""
Simple fixed-wing / UAV kinematic dynamics with maneuver limits.

State (local tangent plane):
    x [m] East, y [m] North, z [m] Up
    psi [rad] heading (yaw)
    v_air [m/s] airspeed (treated as commanded constant or slowly varying)
    E_Wh [Wh] battery energy (optional, if BatteryModel used)

Control (per step):
    psi_cmd [rad] or yaw_rate_cmd [rad/s] (we implement psi_cmd tracking with rate limits)
    vz_cmd [m/s] climb rate command (optional)
    v_air_cmd [m/s] airspeed command (optional)

Maneuver constraints:
- bank angle limit -> max yaw rate approx: yaw_rate_max = g * tan(phi_max) / v_air
- explicit yaw rate limit also supported
- climb rate limit

Wind:
- v_ground = v_air_relative(psi, v_air) + wind(x,y,z,t)

This model is intentionally "simple but explicit" for AeroHack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from mission_framework.aircraft.wind_model import WindModel, ZeroWind


G0 = 9.80665  # m/s^2


def wrap_angle_rad(a: float) -> float:
    """Wrap angle to [-pi, pi]."""
    x = (a + np.pi) % (2.0 * np.pi) - np.pi
    return float(x)


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


@dataclass(frozen=True)
class AircraftParams:
    # Airspeed handling
    v_air_min_mps: float = 12.0
    v_air_max_mps: float = 35.0
    v_air_tau_s: float = 5.0  # first-order lag if v_air_cmd is used

    # Maneuver limits
    bank_max_rad: float = np.deg2rad(30.0)   # max bank angle
    yaw_rate_max_radps: Optional[float] = None  # if set, also clamp yaw rate
    climb_rate_max_mps: float = 3.0
    descent_rate_max_mps: float = 3.0

    # Integration
    dt_s: float = 1.0

    # Optional: altitude band (can be enforced as constraints too)
    z_min_m: Optional[float] = None
    z_max_m: Optional[float] = None


@dataclass
class AircraftState:
    x_m: float
    y_m: float
    z_m: float
    psi_rad: float
    v_air_mps: float


@dataclass(frozen=True)
class AircraftStepResult:
    state: AircraftState
    v_ground_enu_mps: np.ndarray  # (3,)
    v_air_enu_mps: np.ndarray     # (3,)
    wind_enu_mps: np.ndarray      # (3,)
    yaw_rate_radps: float
    climb_rate_mps: float


class AircraftKinematics:
    def __init__(self, params: AircraftParams, wind: Optional[WindModel] = None):
        self.p = params
        self.wind = wind or ZeroWind()

    def yaw_rate_limit_radps(self, v_air_mps: float) -> float:
        v = max(1e-3, float(v_air_mps))
        # coordinated turn approx: psi_dot = g * tan(phi) / v
        lim_bank = G0 * np.tan(self.p.bank_max_rad) / v
        lim = float(lim_bank)
        if self.p.yaw_rate_max_radps is not None:
            lim = min(lim, float(self.p.yaw_rate_max_radps))
        return float(max(1e-6, lim))

    def step(
        self,
        s: AircraftState,
        t_s: float,
        psi_cmd_rad: Optional[float] = None,
        yaw_rate_cmd_radps: Optional[float] = None,
        vz_cmd_mps: float = 0.0,
        v_air_cmd_mps: Optional[float] = None,
    ) -> AircraftStepResult:
        dt = float(self.p.dt_s)

        # --- airspeed update (optional 1st-order lag) ---
        v_air = float(s.v_air_mps)
        if v_air_cmd_mps is not None:
            v_cmd = clamp(float(v_air_cmd_mps), self.p.v_air_min_mps, self.p.v_air_max_mps)
            tau = max(1e-6, float(self.p.v_air_tau_s))
            alpha = 1.0 - np.exp(-dt / tau)
            v_air = (1.0 - alpha) * v_air + alpha * v_cmd
        v_air = clamp(v_air, self.p.v_air_min_mps, self.p.v_air_max_mps)

        # --- heading/yaw rate command ---
        yaw_rate_lim = self.yaw_rate_limit_radps(v_air)

        if yaw_rate_cmd_radps is not None:
            yaw_rate = clamp(float(yaw_rate_cmd_radps), -yaw_rate_lim, yaw_rate_lim)
        elif psi_cmd_rad is not None:
            # simple proportional tracking on wrapped heading error
            err = wrap_angle_rad(float(psi_cmd_rad) - float(s.psi_rad))
            # convert error to rate; clamp by yaw_rate_lim
            # gain ~ 1/dt (aggressive), but limited by yaw_rate_lim anyway
            yaw_rate = clamp(err / max(dt, 1e-6), -yaw_rate_lim, yaw_rate_lim)
        else:
            yaw_rate = 0.0

        psi_next = wrap_angle_rad(float(s.psi_rad) + yaw_rate * dt)

        # --- climb rate command + clamp ---
        vz = clamp(float(vz_cmd_mps), -float(self.p.descent_rate_max_mps), float(self.p.climb_rate_max_mps))

        # --- altitude optional clamp (soft, better enforced as constraints) ---
        z_next = float(s.z_m + vz * dt)
        if self.p.z_min_m is not None:
            z_next = max(float(self.p.z_min_m), z_next)
        if self.p.z_max_m is not None:
            z_next = min(float(self.p.z_max_m), z_next)

        # --- air-relative velocity in ENU from heading ---
        v_air_enu = np.array([v_air * np.sin(psi_next), v_air * np.cos(psi_next), vz], dtype=float)

        # --- wind ---
        w = np.asarray(self.wind.wind_enu(float(s.x_m), float(s.y_m), float(s.z_m), float(t_s)), dtype=float).reshape(3)

        # --- ground velocity ---
        v_ground = v_air_enu + w

        x_next = float(s.x_m + v_ground[0] * dt)
        y_next = float(s.y_m + v_ground[1] * dt)

        s_next = AircraftState(
            x_m=x_next,
            y_m=y_next,
            z_m=z_next,
            psi_rad=psi_next,
            v_air_mps=v_air,
        )

        return AircraftStepResult(
            state=s_next,
            v_ground_enu_mps=v_ground,
            v_air_enu_mps=v_air_enu,
            wind_enu_mps=w,
            yaw_rate_radps=float(yaw_rate),
            climb_rate_mps=float(vz),
        )