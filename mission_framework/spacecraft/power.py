# mission_framework/spacecraft/power.py
"""
Power / battery proxy model (MODULE B / spacecraft).

Purpose:
- Provide a lightweight, scheduler-friendly battery model for CubeSat-style operations.
- Support constraint checks (battery never below 0, optional max, duty cycle).
- Support simulation-in-the-loop scoring (penalize power violations).

Model (simple but credible):
- Battery state of charge (SOC) represented in Wh.
- Charging occurs when in sunlight (eclipse model is handled elsewhere; for now we accept a boolean "in_sun").
- Discharging occurs due to:
    - baseline bus load
    - payload loads during observations
    - radio loads during downlinks
    - attitude slews (optional)

This is designed to integrate with your core SimResult:
- You can store a time series resource "battery_Wh"
- You can store scalars like "min_battery_Wh", "final_battery_Wh"

Notes:
- We do NOT compute sunlight here (that belongs in orbit/illumination or mission simulation).
- For hackathons, you can approximate "in_sun" using a simple duty cycle (e.g., 60% sunlight per orbit),
  or leave it as provided by the visibility / orbit module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class PowerLoads:
    """Power loads in Watts."""
    bus_W: float = 8.0               # always-on avionics + ADCS + compute
    payload_obs_W: float = 18.0      # during observation
    radio_downlink_W: float = 22.0   # during downlink
    slew_W: float = 12.0             # during slews (optional)


@dataclass(frozen=True)
class BatteryConfig:
    capacity_Wh: float = 30.0
    initial_Wh: float = 25.0
    charge_power_W: float = 12.0     # effective net charge power while in sun
    charge_eff: float = 0.95
    discharge_eff: float = 1.00      # keep at 1.0 unless you want losses
    min_Wh: float = 0.0              # hard minimum
    max_Wh: Optional[float] = None   # if None, uses capacity_Wh


@dataclass(frozen=True)
class PowerStep:
    """
    One time interval power context for integration.

    start_s, end_s: interval bounds (seconds)
    in_sun: whether in sunlight for this interval
    mode: high-level activity mode (e.g., "idle", "observe", "downlink", "slew")
    """
    start_s: float
    end_s: float
    in_sun: bool
    mode: str = "idle"


@dataclass(frozen=True)
class PowerTrace:
    """Battery time trace."""
    t_s: np.ndarray           # time stamps (seconds)
    battery_Wh: np.ndarray    # SOC in Wh
    net_power_W: np.ndarray   # positive = charging, negative = discharging

    def min_battery_Wh(self) -> float:
        return float(np.min(self.battery_Wh)) if self.battery_Wh.size else float("inf")

    def final_battery_Wh(self) -> float:
        return float(self.battery_Wh[-1]) if self.battery_Wh.size else float("nan")


class BatteryModel:
    """
    Integrates battery SOC forward over a sequence of PowerSteps.

    Usage:
        model = BatteryModel(cfg, loads)
        trace = model.simulate(steps)
    """

    def __init__(self, cfg: BatteryConfig, loads: PowerLoads = PowerLoads()):
        self.cfg = cfg
        self.loads = loads

    def load_W_for_mode(self, mode: str) -> float:
        """Map a mode string to a total load in Watts."""
        m = (mode or "idle").lower()
        base = float(self.loads.bus_W)
        if m == "idle":
            return base
        if m == "observe":
            return base + float(self.loads.payload_obs_W)
        if m == "downlink":
            return base + float(self.loads.radio_downlink_W)
        if m == "slew":
            return base + float(self.loads.slew_W)
        # unknown mode => just bus
        return base

    def step(
        self,
        battery_Wh: float,
        *,
        dt_s: float,
        in_sun: bool,
        mode: str,
    ) -> Tuple[float, float]:
        """
        Advance battery by dt_s.

        Returns:
            (battery_next_Wh, net_power_W)
        net_power_W: +charge, -discharge (effective)
        """
        dt_h = float(dt_s) / 3600.0
        max_Wh = float(self.cfg.max_Wh) if self.cfg.max_Wh is not None else float(self.cfg.capacity_Wh)

        load_W = self.load_W_for_mode(mode)
        discharge_W = load_W / max(1e-9, float(self.cfg.discharge_eff))

        charge_W = 0.0
        if bool(in_sun):
            charge_W = float(self.cfg.charge_power_W) * float(self.cfg.charge_eff)

        net_W = charge_W - discharge_W
        battery_next = float(battery_Wh + net_W * dt_h)

        # clamp
        battery_next = float(np.clip(battery_next, float(self.cfg.min_Wh), max_Wh))
        return battery_next, float(net_W)

    def simulate(
        self,
        steps: Iterable[PowerStep],
        *,
        dt_internal_s: float = 10.0,
    ) -> PowerTrace:
        """
        Simulate battery over the provided steps.
        Each PowerStep can be long; we integrate it with dt_internal_s to produce a trace.

        dt_internal_s should be coarse enough for speed but fine enough for stability.
        10s is good for 7-day planning traces without huge arrays.
        """
        dt = float(dt_internal_s)
        if dt <= 0:
            raise ValueError("dt_internal_s must be > 0")

        batt = float(self.cfg.initial_Wh)
        max_Wh = float(self.cfg.max_Wh) if self.cfg.max_Wh is not None else float(self.cfg.capacity_Wh)
        batt = float(np.clip(batt, float(self.cfg.min_Wh), max_Wh))

        t_list: List[float] = []
        b_list: List[float] = []
        p_list: List[float] = []

        t_cur = None

        for s in steps:
            t0 = float(s.start_s)
            t1 = float(s.end_s)
            if t1 <= t0:
                continue

            # initialize t_cur to first start
            if t_cur is None:
                t_cur = t0

            # if steps have gaps, coast in "idle" with in_sun=False by default
            if t0 > t_cur:
                gap = t0 - t_cur
                n = int(np.ceil(gap / dt))
                for k in range(n):
                    dt_k = min(dt, gap - k * dt)
                    batt, netW = self.step(batt, dt_s=dt_k, in_sun=False, mode="idle")
                    t_list.append(t_cur + dt_k)
                    b_list.append(batt)
                    p_list.append(netW)
                    t_cur += dt_k

            dur = t1 - t0
            n = int(np.ceil(dur / dt))
            for k in range(n):
                dt_k = min(dt, dur - k * dt)
                batt, netW = self.step(batt, dt_s=dt_k, in_sun=bool(s.in_sun), mode=s.mode)
                t_list.append((t0 + (k * dt) + dt_k))
                b_list.append(batt)
                p_list.append(netW)

            t_cur = t1

        return PowerTrace(
            t_s=np.array(t_list, dtype=float),
            battery_Wh=np.array(b_list, dtype=float),
            net_power_W=np.array(p_list, dtype=float),
        )


# ============================================================
# Simple helpers (scheduler-friendly)
# ============================================================

def make_steps_from_schedule(
    events: Sequence[Tuple[float, float, str]],
    *,
    sunlight_fn: Optional[Callable[[float], bool]] = None,
    default_in_sun: bool = True,
) -> List[PowerStep]:
    """
    Convert a simple list of events (t_start, t_end, mode) into PowerSteps.

    sunlight_fn(t_mid_s)->bool can be used if you have an eclipse model.
    If not provided, uses default_in_sun.
    """
    steps: List[PowerStep] = []
    for (t0, t1, mode) in events:
        t0f = float(t0)
        t1f = float(t1)
        if t1f <= t0f:
            continue
        tmid = 0.5 * (t0f + t1f)
        in_sun = bool(sunlight_fn(tmid)) if sunlight_fn is not None else bool(default_in_sun)
        steps.append(PowerStep(start_s=t0f, end_s=t1f, in_sun=in_sun, mode=str(mode)))
    return steps