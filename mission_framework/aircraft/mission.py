# mission_framework/aircraft/mission.py
"""
Waypoint mission definition + Problem builder (MODULE A / aircraft).

This module defines:
- Waypoints (declarative targets)
- Missions (ordered list of waypoints + metadata)
- build_problem_from_config(cfg): YAML -> unified core Problem (Planner-ready)

Coordinates:
- Flat-earth planar frame: x,y in meters; z in meters (altitude, positive up).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import math
import numpy as np

from mission_framework.core.decision_variables import Bounds, ContinuousVar, DecisionAssignment, DecisionSpace, PermutationVar
from mission_framework.core.objective import Objective, term_minimize_energy, term_minimize_time
from mission_framework.core.planner import Problem
from mission_framework.core.types import Plan, SimResult

from mission_framework.aircraft.model import AircraftParams, AircraftSim
from mission_framework.aircraft.wind import NoWind, SinusoidalWind
from mission_framework.aircraft.energy import EnergyModel
from mission_framework.aircraft.geofence import GeofenceMap, NoFlyZone
from mission_framework.aircraft.constraints import default_aircraft_constraints


# ============================================================
# Helpers
# ============================================================

def _dist3(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


# ============================================================
# Waypoints / Missions (declarative)
# ============================================================

@dataclass(frozen=True)
class Waypoint:
    """
    A mission waypoint.

    Required:
      x, y, z: target location [m]

    Optional "hints"/constraints:
      radius_m:      capture radius for considering it reached
      target_speed:  desired speed near waypoint [m/s]
      min_speed/max_speed: allowable speed near waypoint [m/s]
      min_alt/max_alt: allowable altitude near waypoint [m]
      loiter_time_s: time to loiter after reaching waypoint [s]
      name:          identifier
      tags:          free-form metadata (e.g., "inspect", "drop", "handoff")
    """
    x: float
    y: float
    z: float = 0.0

    radius_m: float = 10.0

    target_speed: Optional[float] = None
    min_speed: Optional[float] = None
    max_speed: Optional[float] = None

    min_alt: Optional[float] = None
    max_alt: Optional[float] = None

    loiter_time_s: float = 0.0

    name: str = ""
    tags: Dict[str, object] = field(default_factory=dict)

    def pos3(self) -> Tuple[float, float, float]:
        return float(self.x), float(self.y), float(self.z)

    def pos2(self) -> Tuple[float, float]:
        return float(self.x), float(self.y)


@dataclass(frozen=True)
class Mission:
    """
    An ordered list of waypoints.

    mission_id: unique identifier
    waypoints: ordered list
    metadata: free-form mission metadata (client, payload, etc.)
    """
    waypoints: Tuple[Waypoint, ...]
    mission_id: str = "mission"
    metadata: Dict[str, object] = field(default_factory=dict)


# ============================================================
# YAML -> Problem builder (realistic point-mass sim)
# ============================================================

def build_problem_from_config(cfg: Dict[str, Any]) -> Problem:
    """
    Build a unified-core Problem for the aircraft scenario.

    Decision variables (minimal but meaningful):
    - visit_order: permutation of required waypoints
    - cruise_speed_mps: nominal commanded airspeed

    Planning loop:
    assignment -> build_plan() -> AircraftSim.simulate() -> constraints + objective
    """
    scenario = cfg.get("scenario", {}) or {}
    if str(scenario.get("type", "")).lower() != "aircraft":
        raise ValueError("build_problem_from_config called with non-aircraft scenario")

    # --- Parse waypoints ---
    wps_yaml = (cfg.get("mission", {}) or {}).get("waypoints", []) or []
    if not wps_yaml:
        raise ValueError("aircraft scenario requires mission.waypoints")

    waypoints = tuple(
        Waypoint(
            x=float(w["x_m"]),
            y=float(w["y_m"]),
            z=float(w.get("z_m", 0.0)),
            name=str(w.get("id", "")),
            radius_m=float(w.get("radius_m", 10.0)),
        )
        for w in wps_yaml
    )
    mission = Mission(
        waypoints=waypoints,
        mission_id=str(scenario.get("name", "aircraft_demo")),
    )

    # --- Vehicle parameters ---
    vcfg = cfg.get("vehicle", {}) or {}
    min_v = float(vcfg.get("min_speed_mps", 12.0))
    max_v = float(vcfg.get("max_speed_mps", 30.0))
    cruise_default = float(vcfg.get("cruise_speed_mps", (min_v + max_v) / 2.0))

    # --- Decision space ---
    wp_ids = [wp.name or f"WP{i}" for i, wp in enumerate(mission.waypoints)]
    ds = DecisionSpace(
        variables=[
            PermutationVar("visit_order", items=wp_ids),
            ContinuousVar("cruise_speed_mps", bounds=Bounds(min_v, max_v)),
        ]
    )

    # --- Wind model ---
    wcfg = cfg.get("wind", {}) or {}
    wtype = str(wcfg.get("type", "sinusoidal")).lower()
    if wtype == "none" or wtype == "no_wind":
        wind = NoWind()
    else:
        wind = SinusoidalWind(
            base_speed_mps=float(wcfg.get("base_speed_mps", 5.0)),
            direction_rad=float(wcfg.get("direction_rad", 0.0)),
            gust_amplitude_mps=float(wcfg.get("gust_amplitude_mps", 2.0)),
            gust_frequency_hz=float(wcfg.get("gust_frequency_hz", 0.005)),
        )

    # --- Energy model (simple but credible) ---
    # Use YAML "energy_rate_cruise_W" as base load if present.
    p_base = float(vcfg.get("energy_rate_cruise_W", 250.0))
    energy = EnergyModel(p_base_W=p_base)

    # --- Geofence map ---
    gcfg = cfg.get("geofence", {}) or {}
    zones_yaml = gcfg.get("no_fly_zones", []) or []
    zones = []
    for z in zones_yaml:
        poly = [(float(p[0]), float(p[1])) for p in (z.get("polygon", []) or [])]
        if len(poly) >= 3:
            zones.append(NoFlyZone(zone_id=str(z.get("id", "NFZ")), polygon=poly))
    geofence = GeofenceMap(zones=zones) if zones else None

    # --- Simulator params ---
    ic = cfg.get("initial_state", {}) or {}
    batt_cap = float(vcfg.get("battery_capacity_Wh", float(ic.get("battery_Wh", 800.0))))
    params = AircraftParams(
        min_speed_mps=min_v,
        max_speed_mps=max_v,
        max_turn_rate_radps=float(vcfg.get("max_turn_rate_radps", 0.35)),
        battery_capacity_Wh=batt_cap,
        dt_s=float(vcfg.get("dt_s", 1.0)),
        reach_radius_m=float(vcfg.get("reach_radius_m", 15.0)),
    )
    sim_engine = AircraftSim(params=params, wind=wind, energy=energy, geofence=geofence)

    # --- Build plan from decisions ---
    def build_plan(a: DecisionAssignment) -> Plan:
        order = list(a["visit_order"])
        cruise_speed = float(np.array(a["cruise_speed_mps"]).reshape(-1)[0])

        name_to_wp = {wp.name: wp for wp in mission.waypoints}
        ordered = [name_to_wp[n] for n in order]

        x0 = float(ic.get("x_m", 0.0))
        y0 = float(ic.get("y_m", 0.0))

        # Plan.waypoints is an ordered list of dicts (reporting-friendly).
        rows = [{"id": "START", "x_m": x0, "y_m": y0, "z_m": float(ic.get("z_m", 0.0)), "eta_s": 0.0}]
        t = 0.0
        for wp in ordered:
            d = _dist2((x0, y0), (wp.x, wp.y))
            dt = d / max(1e-6, cruise_speed)
            t += dt
            rows.append({"id": wp.name, "x_m": float(wp.x), "y_m": float(wp.y), "z_m": float(wp.z), "eta_s": float(t)})
            x0, y0 = wp.x, wp.y

        # Put "execution parameters" in metadata so the simulator can use them.
        plan = Plan(
            kind="aircraft",
            waypoints=rows,
            metadata={
                "mission_id": mission.mission_id,
                "cruise_speed_mps": float(cruise_speed),
                # initial conditions (used by sim)
                "heading_rad": float(ic.get("heading_rad", 0.0)),
                "speed_mps": float(ic.get("speed_mps", cruise_default)),
                "battery_Wh": float(ic.get("battery_Wh", batt_cap)),
            },
        )
        return plan

    # --- Simulation wrapper (Plan -> SimResult) ---
    def simulate(plan: Plan, rng: np.random.Generator | None) -> SimResult:
        # Large cap; sim stops when final waypoint reached or battery depleted.
        return sim_engine.simulate(plan, rng=rng, t_max_s=4_000.0)

    # --- Constraints ---
    cflags = cfg.get("constraints", {}) or {}
    enforce_geofence = bool(cflags.get("enforce_geofence", True))
    constraints = default_aircraft_constraints(enforce_geofence=enforce_geofence)

    # --- Objective ---
    obj_cfg = cfg.get("objective", {}) or {}
    terms_cfg = obj_cfg.get("terms", []) or []
    objective = Objective()

    if terms_cfg:
        for term in terms_cfg:
            tname = str(term.get("name", "")).strip()
            weight = float(term.get("weight", 1.0))
            mode = str(term.get("mode", "minimize")).lower()

            # We support your YAML names by mapping to sim.scalars keys
            if tname in ("total_time", "time", "t_end_s"):
                objective.add(term_minimize_time(name="time", weight=weight, key="t_end_s"))
            elif tname in ("energy_used", "energy", "energy_used_Wh"):
                objective.add(term_minimize_energy(name="energy", weight=weight, key="energy_used_Wh"))
            else:
                # Unknown term name: ignore (or raise if you want strict configs)
                continue
    else:
        # Default: minimize time
        objective.add(term_minimize_time(name="time", weight=1.0, key="t_end_s"))

    return Problem(
        decision_space=ds,
        build_plan=build_plan,
        simulate=simulate,
        constraints=constraints,  # Sequence[Constraint] recommended in Problem typing
        objective=objective,
        robustness_cases=0,
        metadata={"mission_id": mission.mission_id},
    )