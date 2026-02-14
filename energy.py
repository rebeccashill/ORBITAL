# mission_framework/aircraft/energy.py
"""
Fuel/battery consumption model (MODULE A / aircraft).

This module provides simple, optimization-friendly energy models for a point-mass UAV.
It is meant to be used alongside aircraft/model.py (kinematics) and wind.py (wind fields).

Design goals:
- cheap to evaluate (planner-friendly)
- monotonic / smooth-ish costs
- easily swappable (fuel vs battery vs hybrid)

Conventions:
- v_air: airspeed magnitude [m/s]
- v_ground: ground speed magnitude [m/s]
- climb_rate: vertical speed [m/s] (positive up)
- dt: timestep [s]

You can call:
- step_energy(...) -> EnergyStep
- integrate_energy(...) over a trajectory
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import math


# ============================================================
# Helpers
# ============================================================

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def norm2(x: float, y: float) -> float:
    return math.sqrt(x * x + y * y)


# ============================================================
# Data structures
# ============================================================

@dataclass(frozen=True)
class EnergyStep:
    """
    Energy accounting for a single step.

    For fuel:
      fuel_used is in "fuel units" (could be kg, liters, or abstract units).
    For battery:
      energy_used is in Joules or Wh depending on your convention.
    """
    fuel_used: float
    energy_used: float
    power: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "fuel_used": float(self.fuel_used),
            "energy_used": float(self.energy_used),
            "power": float(self.power),
        }


@dataclass(frozen=True)
class EnergyTotals:
    fuel_used: float
    energy_used: float
    avg_power: float
    peak_power: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "fuel_used": float(self.fuel_used),
            "energy_used": float(self.energy_used),
            "avg_power": float(self.avg_power),
            "peak_power": float(self.peak_power),
        }


# ============================================================
# Models
# ============================================================

@dataclass(frozen=True)
class FuelModelParams:
    """
    Very simple fuel flow model.

    fuel_flow = c0 + c1*v_air + c2*v_air^2 + c_climb*max(0, climb_rate)

    Units are intentionally abstract; tune constants to match your scenario.
    """
    c0: float = 0.01      # baseline fuel flow [fuel/s]
    c1: float = 0.0005    # linear term [fuel/(m)]
    c2: float = 0.00005   # quadratic term [fuel/(m^2)]
    c_climb: float = 0.002  # extra fuel per climb m/s [fuel/s per (m/s)]
    min_flow: float = 0.0


@dataclass(frozen=True)
class BatteryModelParams:
    """
    Simple electric power model.

    power = p0 + p1*v_air + p2*v_air^2 + p_climb*max(0, climb_rate)

    energy_used = power * dt

    Units: Watts for power if you choose; energy in Joules.
    """
    p0: float = 80.0       # idle/avionics [W]
    p1: float = 2.0        # [W per (m/s)]
    p2: float = 0.5        # [W per (m/s)^2]
    p_climb: float = 60.0  # [W per (m/s)] for positive climb
    min_power: float = 0.0


def fuel_step(
    *,
    v_air: float,
    climb_rate: float,
    dt: float,
    params: FuelModelParams = FuelModelParams(),
) -> EnergyStep:
    """Compute fuel usage for one timestep."""
    v_air = max(0.0, float(v_air))
    climb = max(0.0, float(climb_rate))
    dt = max(0.0, float(dt))

    flow = params.c0 + params.c1 * v_air + params.c2 * (v_air * v_air) + params.c_climb * climb
    flow = max(float(params.min_flow), float(flow))

    fuel_used = flow * dt

    # For fuel-only model, we can optionally map fuel flow to "power-like" for consistency.
    # Keep it simple: treat fuel_used as primary and set energy/power to 0.
    return EnergyStep(fuel_used=float(fuel_used), energy_used=0.0, power=0.0)


def battery_step(
    *,
    v_air: float,
    climb_rate: float,
    dt: float,
    params: BatteryModelParams = BatteryModelParams(),
) -> EnergyStep:
    """Compute battery energy usage for one timestep."""
    v_air = max(0.0, float(v_air))
    climb = max(0.0, float(climb_rate))
    dt = max(0.0, float(dt))

    power = params.p0 + params.p1 * v_air + params.p2 * (v_air * v_air) + params.p_climb * climb
    power = max(float(params.min_power), float(power))

    energy_used = power * dt  # Joules if power is Watts

    return EnergyStep(fuel_used=0.0, energy_used=float(energy_used), power=float(power))


# ============================================================
# Integration over a trajectory
# ============================================================

def integrate_fuel(
    v_air: Iterable[float],
    climb_rate: Iterable[float],
    *,
    dt: float,
    params: FuelModelParams = FuelModelParams(),
) -> EnergyTotals:
    """Integrate fuel usage over sequences of v_air and climb_rate."""
    dt = max(0.0, float(dt))
    total_fuel = 0.0

    peak_power = 0.0
    power_sum = 0.0
    n = 0

    for va, vz in zip(v_air, climb_rate):
        step = fuel_step(v_air=float(va), climb_rate=float(vz), dt=dt, params=params)
        total_fuel += step.fuel_used
        # No power in fuel model by default; keep bookkeeping anyway
        peak_power = max(peak_power, step.power)
        power_sum += step.power
        n += 1

    avg_power = power_sum / n if n > 0 else 0.0
    return EnergyTotals(
        fuel_used=float(total_fuel),
        energy_used=0.0,
        avg_power=float(avg_power),
        peak_power=float(peak_power),
    )


def integrate_battery(
    v_air: Iterable[float],
    climb_rate: Iterable[float],
    *,
    dt: float,
    params: BatteryModelParams = BatteryModelParams(),
) -> EnergyTotals:
    """Integrate battery energy usage over sequences of v_air and climb_rate."""
    dt = max(0.0, float(dt))
    total_energy = 0.0

    peak_power = 0.0
    power_sum = 0.0
    n = 0

    for va, vz in zip(v_air, climb_rate):
        step = battery_step(v_air=float(va), climb_rate=float(vz), dt=dt, params=params)
        total_energy += step.energy_used
        peak_power = max(peak_power, step.power)
        power_sum += step.power
        n += 1

    avg_power = power_sum / n if n > 0 else 0.0
    return EnergyTotals(
        fuel_used=0.0,
        energy_used=float(total_energy),
        avg_power=float(avg_power),
        peak_power=float(peak_power),
    )


# ============================================================
# Convenience: derive v_air & climb_rate from state history
# ============================================================

def airspeed_and_climb_from_states(
    states: Iterable[object],
    *,
    fallback_v_key: str = "v",
) -> Tuple[list, list]:
    """
    Convenience helper for common state objects (like AircraftState from model.py).
    Returns lists (v_air_list, climb_rate_list) using:
      - v_air: state.v or getattr(state, fallback_v_key)
      - climb_rate: finite difference of z if z exists
    """
    states_list = list(states)
    if not states_list:
        return [], []

    v_air = []
    z = []

    for s in states_list:
        v_air.append(float(getattr(s, "v", getattr(s, fallback_v_key, 0.0))))
        z.append(float(getattr(s, "z", 0.0)))

    climb_rate = [0.0]
    for i in range(1, len(z)):
        climb_rate.append(z[i] - z[i - 1])  # caller divides by dt if desired

    return v_air, climb_rate
