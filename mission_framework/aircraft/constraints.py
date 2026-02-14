# mission_framework/aircraft/constraints.py
"""
Aircraft-specific constraint wrappers (MODULE A / aircraft).

This module adapts aircraft missions/sim results into the generic constraint system
defined in mission_framework/core/constraints.py.

Pattern:
- core/constraints.py defines the generic Constraint interface and reporting
- aircraft/constraints.py defines common UAV constraints and helper factories

Expected simulation result shape (flexible):
- sim.states: sequence of state objects with x,y,z,v,psi (see aircraft/model.py)
- sim.times:  sequence of float times aligned with states
- sim.controls: optional sequence of controls with v_cmd, psi_rate_cmd, vz_cmd
- sim.fuel_remaining / sim.fuel_initial: optional, for fuel constraints
- sim.energy_remaining / sim.energy_initial: optional, for battery constraints

Geofences:
- Uses aircraft/geofence.py PolygonFence(s)
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

import math

from mission_framework.core.constraints import Constraint, Severity

from mission_framework.aircraft.geofence import PolygonFence, path_violates_any_fence
from mission_framework.aircraft.mission import Mission, Waypoint, reached_waypoint


# ============================================================
# Internal utilities
# ============================================================

def _states(sim) -> List[object]:
    s = getattr(sim, "states", None)
    if s is None:
        raise AttributeError("Simulation result must have `states`.")
    return list(s)


def _times(sim) -> List[float]:
    t = getattr(sim, "times", None)
    if t is None:
        # allow fallback if sim has timeline.t
        if hasattr(sim, "timeline") and hasattr(sim.timeline, "t"):
            return list(sim.timeline.t)
        raise AttributeError("Simulation result must have `times` (or `timeline.t`).")
    return list(t)


def _xy_path(sim) -> List[Tuple[float, float]]:
    pts = []
    for s in _states(sim):
        pts.append((float(getattr(s, "x")), float(getattr(s, "y"))))
    return pts


def _z_hist(sim) -> List[float]:
    return [float(getattr(s, "z", 0.0)) for s in _states(sim)]


def _v_hist(sim) -> List[float]:
    return [float(getattr(s, "v", 0.0)) for s in _states(sim)]


def _fuel_remaining(sim) -> Optional[float]:
    if hasattr(sim, "fuel_remaining"):
        return float(getattr(sim, "fuel_remaining"))
    return None


def _energy_remaining(sim) -> Optional[float]:
    if hasattr(sim, "energy_remaining"):
        return float(getattr(sim, "energy_remaining"))
    return None


# ============================================================
# Constraint factories
# ============================================================

def no_geofence_violation(
    fences: Sequence[PolygonFence],
    *,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "no_geofence_violation",
) -> Constraint:
    """
    HARD: path must not enter or cross any no-fly polygon.

    Margin definition:
      +inf  if no violation
      -1.0  if violated (binary)
    """
    def _fn(sim) -> float:
        viol = path_violates_any_fence(_xy_path(sim), fences)
        return float("inf") if viol is None else -1.0

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def altitude_bounds(
    *,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "altitude_bounds",
) -> Constraint:
    """
    Enforce altitude bounds over the full trajectory.

    Margin is the *worst* margin across time:
      margin = min( min(z - z_min), min(z_max - z) )
    """
    def _fn(sim) -> float:
        zs = _z_hist(sim)
        m = float("inf")
        if z_min is not None:
            m = min(m, min(z - float(z_min) for z in zs))
        if z_max is not None:
            m = min(m, min(float(z_max) - z for z in zs))
        return float(m)

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def speed_bounds(
    *,
    v_min: Optional[float] = None,
    v_max: Optional[float] = None,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "speed_bounds",
) -> Constraint:
    """
    Enforce airspeed bounds over the full trajectory.

    Margin = min( min(v - v_min), min(v_max - v) )
    """
    def _fn(sim) -> float:
        vs = _v_hist(sim)
        m = float("inf")
        if v_min is not None:
            m = min(m, min(v - float(v_min) for v in vs))
        if v_max is not None:
            m = min(m, min(float(v_max) - v for v in vs))
        return float(m)

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def nonnegative_fuel(
    *,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "nonnegative_fuel",
) -> Constraint:
    """
    Fuel must not go below zero.

    If sim tracks fuel_remaining, margin = fuel_remaining (>=0).
    If not available, returns +inf (constraint effectively inactive).
    """
    def _fn(sim) -> float:
        fr = _fuel_remaining(sim)
        if fr is None:
            return float("inf")
        return float(fr)

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def nonnegative_energy(
    *,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "nonnegative_energy",
) -> Constraint:
    """
    Battery/energy must not go below zero.

    If sim tracks energy_remaining, margin = energy_remaining (>=0).
    If not available, returns +inf (inactive).
    """
    def _fn(sim) -> float:
        er = _energy_remaining(sim)
        if er is None:
            return float("inf")
        return float(er)

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def mission_completed(
    mission: Mission,
    *,
    final_radius_override: Optional[float] = None,
    severity: Severity = Severity.HARD,
    weight: float = 1.0,
    name: str = "mission_completed",
) -> Constraint:
    """
    Require the final waypoint to be reached by the end of the sim.

    Margin = (radius - distance_to_final) so >=0 means reached.
    """
    final_wp: Waypoint = mission.waypoints[-1]
    radius = float(final_radius_override) if final_radius_override is not None else float(final_wp.radius_m)

    def _fn(sim) -> float:
        s_last = _states(sim)[-1]
        pos = (float(getattr(s_last, "x")), float(getattr(s_last, "y")), float(getattr(s_last, "z", 0.0)))
        dx = pos[0] - float(final_wp.x)
        dy = pos[1] - float(final_wp.y)
        dz = pos[2] - float(final_wp.z)
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        return float(radius - dist)

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


def waypoint_sequence_reached(
    mission: Mission,
    *,
    severity: Severity = Severity.SOFT,
    weight: float = 1.0,
    name: str = "waypoint_sequence_reached",
) -> Constraint:
    """
    SOFT: encourage reaching as many waypoints as possible in order.

    Margin definition:
      margin = (num_reached - (N-1))  -> >=0 means all reached
    This makes it easy to interpret as a constraint-like goal.
    """
    wps = list(mission.waypoints)

    def _fn(sim) -> float:
        states = _states(sim)
        idx = 0
        for s in states:
            pos = (float(getattr(s, "x")), float(getattr(s, "y")), float(getattr(s, "z", 0.0)))
            if reached_waypoint(pos, wps[idx]):
                if idx < len(wps) - 1:
                    idx += 1
                else:
                    break
        # idx is final reached index; count reached = idx+1 if started at 0
        reached_count = idx + 1
        return float(reached_count - (len(wps)))

    return Constraint(name=name, fn=_fn, severity=severity, weight=weight)


# ============================================================
# Convenience bundles
# ============================================================

def default_aircraft_constraints(
    mission: Mission,
    fences: Optional[Sequence[PolygonFence]] = None,
    *,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
    v_min: Optional[float] = None,
    v_max: Optional[float] = None,
    require_fuel_nonnegative: bool = True,
    require_energy_nonnegative: bool = False,
) -> List[Constraint]:
    """
    Handy starter set of constraints for aircraft missions.
    """
    out: List[Constraint] = []

    out.append(mission_completed(mission, severity=Severity.HARD))

    if fences:
        out.append(no_geofence_violation(fences, severity=Severity.HARD))

    if z_min is not None or z_max is not None:
        out.append(altitude_bounds(z_min=z_min, z_max=z_max, severity=Severity.HARD))

    if v_min is not None or v_max is not None:
        out.append(speed_bounds(v_min=v_min, v_max=v_max, severity=Severity.HARD))

    if require_fuel_nonnegative:
        out.append(nonnegative_fuel(severity=Severity.HARD))

    if require_energy_nonnegative:
        out.append(nonnegative_energy(severity=Severity.HARD))

    # soft encouragement: reach more waypoints even if mission not completed
    out.append(waypoint_sequence_reached(mission, severity=Severity.SOFT, weight=0.2))

    return out
