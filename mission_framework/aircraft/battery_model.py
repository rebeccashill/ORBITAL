# mission_framework/aircraft/battery_model.py
"""
Battery / endurance model for aircraft (UAV/fixed-wing).

This is deliberately "simple but explicit" for AeroHack:
- tracks battery energy [Wh]
- defines power draw [W] based on airspeed and climb rate proxies
- integrates energy over time during simulation

Battery constraint becomes trivial:
    battery_Wh(t) >= 0  for all t
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class BatteryParams:
    capacity_Wh: float = 200.0          # total energy
    initial_Wh: Optional[float] = None  # defaults to capacity

    # Simple power model: P = P0 + k_v * v^2 + k_climb * max(0, climb_rate)
    # (These are proxy coefficients; tune for your demo.)
    p_idle_W: float = 60.0              # avionics + baseline propulsion
    k_v_W_per_m2s2: float = 1.0         # scales with v_air^2
    k_climb_W_per_mps: float = 120.0    # extra power per m/s climb (proxy)

    # Optional: penalize aggressive turning a bit (banking induced drag proxy)
    k_turn_W_per_radps: float = 30.0    # extra power per |yaw_rate|


@dataclass
class BatteryState:
    energy_Wh: float


class BatteryModel:
    def __init__(self, params: BatteryParams):
        self.p = params
        init = self.p.capacity_Wh if self.p.initial_Wh is None else float(self.p.initial_Wh)
        if init < 0 or init > self.p.capacity_Wh:
            raise ValueError("initial_Wh must be within [0, capacity_Wh]")
        self.state = BatteryState(energy_Wh=init)
        self.energy_used_Wh: float = 0.0

    def reset(self) -> None:
        init = self.p.capacity_Wh if self.p.initial_Wh is None else float(self.p.initial_Wh)
        self.state = BatteryState(energy_Wh=init)
        self.energy_used_Wh = 0.0

    def power_W(
        self,
        v_air_mps: float,
        climb_rate_mps: float = 0.0,
        yaw_rate_radps: float = 0.0,
    ) -> float:
        """
        Proxy electrical power draw in watts.

        v_air_mps: air-relative speed (not ground speed), so wind affects energy indirectly.
        climb_rate_mps: positive climb increases power.
        yaw_rate_radps: absolute yaw rate increases power slightly (proxy for induced drag).
        """
        v = float(max(0.0, v_air_mps))
        climb = float(max(0.0, climb_rate_mps))
        turn = float(abs(yaw_rate_radps))

        P = (
            self.p.p_idle_W
            + self.p.k_v_W_per_m2s2 * (v * v)
            + self.p.k_climb_W_per_mps * climb
            + self.p.k_turn_W_per_radps * turn
        )
        return float(max(0.0, P))

    def step(
        self,
        dt_s: float,
        v_air_mps: float,
        climb_rate_mps: float = 0.0,
        yaw_rate_radps: float = 0.0,
    ) -> BatteryState:
        """
        Integrate battery energy forward by dt_s.
        Returns updated state.
        """
        dt = float(dt_s)
        if dt <= 0:
            return self.state

        P = self.power_W(v_air_mps, climb_rate_mps, yaw_rate_radps)  # W = J/s
        dE_Wh = (P * dt) / 3600.0

        self.state.energy_Wh -= dE_Wh
        self.energy_used_Wh += dE_Wh
        return self.state

    def snapshot(self) -> dict:
        return {
            "battery_Wh": float(self.state.energy_Wh),
            "energy_used_Wh": float(self.energy_used_Wh),
            "capacity_Wh": float(self.p.capacity_Wh),
        }


# Convenience: compute a full battery trace after sim (if you didn’t integrate online)
def integrate_battery_trace(
    t_s: np.ndarray,
    v_air_mps: np.ndarray,
    climb_rate_mps: Optional[np.ndarray] = None,
    yaw_rate_radps: Optional[np.ndarray] = None,
    params: Optional[BatteryParams] = None,
) -> dict:
    """
    Offline integration helper.
    Returns {battery_Wh: array, energy_used_Wh: scalar}.
    """
    params = params or BatteryParams()
    bm = BatteryModel(params)
    bm.reset()

    t = np.asarray(t_s, dtype=float).reshape(-1)
    v = np.asarray(v_air_mps, dtype=float).reshape(-1)

    cr = np.zeros_like(v) if climb_rate_mps is None else np.asarray(climb_rate_mps, dtype=float).reshape(-1)
    yr = np.zeros_like(v) if yaw_rate_radps is None else np.asarray(yaw_rate_radps, dtype=float).reshape(-1)

    if not (t.size == v.size == cr.size == yr.size):
        raise ValueError("All input arrays must have the same length.")

    battery = np.zeros_like(t)
    battery[0] = bm.state.energy_Wh

    for i in range(1, t.size):
        dt = t[i] - t[i - 1]
        bm.step(dt, v[i - 1], cr[i - 1], yr[i - 1])
        battery[i] = bm.state.energy_Wh

    return {
        "battery_Wh": battery,
        "energy_used_Wh": float(bm.energy_used_Wh),
        "capacity_Wh": float(params.capacity_Wh),
    }