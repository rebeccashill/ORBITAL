# mission_framework/aircraft/mission.py
"""
Waypoint mission definition + Problem builder (MODULE A / aircraft).

UPDATED for AeroHack readiness:
- Uses new wind_model.py (ZeroWind / SinusoidalWind / VortexFieldWind / StochasticWind)
- Uses new AircraftSim in aircraft/model.py (wind + battery + maneuver limits + geofence audit)
- Builds explicit HARD constraints (battery >= 0, all waypoints reached, geofence clearance, yaw-rate limit)
- Objective uses shared core/objective.py terms (time / energy)

Coordinates:
- Flat-earth planar frame: x,y in meters; z in meters (altitude, positive up).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, List, Union

import math
import numpy as np

from mission_framework.core.decision_variables import (
    Bounds,
    ContinuousVar,
    DecisionAssignment,
    DecisionSpace,
    PermutationVar,
)
from mission_framework.core.objective import Objective, term_minimize_energy, term_minimize_time
from mission_framework.core.planner import Problem
from mission_framework.core.types import Plan, SimResult
from mission_framework.core.constraints import (
    Constraint,
    ConstraintGroup,
    FunctionalConstraint,
    Severity,
    margin_geq,
)

from mission_framework.aircraft.model import AircraftSim, AircraftSimParams
from mission_framework.aircraft.dynamics import AircraftParams as DynParams, G0
from mission_framework.aircraft.wind_model import (
    ZeroWind,
    UniformWind,
    SinusoidalWind,
    VortexFieldWind,
    StochasticWind,
)
from mission_framework.aircraft.battery_model import BatteryParams
from mission_framework.aircraft.geofence import GeofenceMap, NoFlyZone

# ============================================================
# Helpers
# ============================================================


def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


# ============================================================
# Waypoints / Missions (declarative)
# ============================================================


@dataclass(frozen=True)
class Waypoint:
    x: float
    y: float
    z: float = 0.0
    radius_m: float = 10.0
    name: str = ""
    tags: Dict[str, object] = field(default_factory=dict)

    def pos2(self) -> Tuple[float, float]:
        return float(self.x), float(self.y)


@dataclass(frozen=True)
class Mission:
    waypoints: Tuple[Waypoint, ...]
    mission_id: str = "mission"
    metadata: Dict[str, object] = field(default_factory=dict)


# ============================================================
# Constraint constructors (aircraft-specific, core-compatible)
# ============================================================


def _aircraft_constraints_from_cfg(cfg: Dict[str, Any]) -> List[Constraint | ConstraintGroup]:
    """
    Build AeroHack-visible constraints with clear, auditable margins.

    Expected SimResult fields produced by aircraft/model.py:
      - sim.t (timeline)
      - sim.trajectory.state[:, ...] including battery_Wh at index 5
      - sim.resources["yaw_rate_radps"] (array)
      - sim.scalars["waypoints_completed"], sim.scalars["waypoints_total"]
      - sim.scalars["geofence_violated"], sim.scalars["geofence_min_clearance_m"]
    """
    constraints_cfg = cfg.get("constraints", {}) or {}

    # Battery must never drop below 0
    def battery_margin(sim: SimResult) -> np.ndarray:
        batt = np.asarray(sim.resources.get("battery_Wh", []), dtype=float).reshape(-1)

        if batt.size == 0:
            # Defensive fallback so planner penalizes
            return np.array([-1.0], dtype=float)

        return margin_geq(batt, 0.0)

    c_batt = FunctionalConstraint(
        name="battery_nonnegative",
        fn=battery_margin,
        severity=Severity.HARD,
        metadata={
            "t": lambda sim: sim.t
        },  # lightweight hint; constraints system may ignore callables
    )

    # Must reach all waypoints
    def wp_complete_margin(sim: SimResult) -> np.ndarray:
        reached_all = bool(sim.metadata.get("reached_all", False))
        return np.array([1.0 if reached_all else -1.0], dtype=float)

    c_wp = FunctionalConstraint(
        name="all_waypoints_reached",
        fn=wp_complete_margin,
        severity=Severity.HARD,
    )

    # Geofence: must not violate AND (optionally) maintain clearance buffer
    enforce_geofence = bool(constraints_cfg.get("enforce_geofence", True))
    clearance_m = float((cfg.get("geofence", {}) or {}).get("clearance_m", 0.0))

    def geofence_violation_margin(sim: SimResult) -> np.ndarray:
        # geofence_violated scalar is 1.0 when violated
        v = float(sim.scalars.get("geofence_violated", 0.0))
        # margin >=0 when v==0
        return np.array([0.5 - v], dtype=float)  # if v=0 -> +0.5; if v=1 -> -0.5

    def geofence_clearance_margin(sim: SimResult) -> np.ndarray:
        mc = float(sim.scalars.get("geofence_min_clearance_m", float("inf")))
        return np.array([mc - clearance_m], dtype=float)

    c_geo = FunctionalConstraint(
        name="geofence_no_entry",
        fn=geofence_violation_margin,
        severity=Severity.HARD,
    )
    c_clear = FunctionalConstraint(
        name="geofence_clearance",
        fn=geofence_clearance_margin,
        severity=Severity.HARD,
    )

    # Maneuver: yaw-rate limited by bank angle and speed
    # yaw_rate_max = g * tan(phi_max) / v_air
    dyn_cfg = cfg.get("vehicle", {}) or {}
    bank_max_deg = float(dyn_cfg.get("bank_max_deg", 30.0))
    bank_max_rad = math.radians(bank_max_deg)

    def yaw_rate_margin(sim: SimResult) -> np.ndarray:
        yaw_rate = np.asarray(sim.resources.get("yaw_rate_radps", []), dtype=float).reshape(-1)
        v_air = np.asarray(sim.resources.get("v_air_mps", []), dtype=float).reshape(-1)

        if yaw_rate.size == 0 or v_air.size == 0:
            # fail-safe: return a single negative margin so planner penalizes
            return np.array([-1.0], dtype=float)

        v_air = np.maximum(v_air, 1e-3)
        yaw_rate_lim = (G0 * math.tan(bank_max_rad)) / v_air

        return yaw_rate_lim - np.abs(yaw_rate)

    c_turn = FunctionalConstraint(
        name="bank_angle_turn_limit",
        fn=yaw_rate_margin,
        severity=Severity.HARD,
        metadata={"bank_max_deg": bank_max_deg},
    )

    items: List[Constraint | ConstraintGroup] = [c_batt, c_wp, c_turn]

    if enforce_geofence:
        # Group to keep reporting tidy
        items.append(ConstraintGroup("geofence", [c_geo, c_clear]))

    return items


# ============================================================
# YAML -> Problem builder (realistic point-mass sim)
# ============================================================


def build_problem_from_config(cfg: Dict[str, Any]) -> Problem:
    """
    Build a unified-core Problem for the aircraft scenario.

    Decision variables (minimal but meaningful):
    - visit_order: permutation of required waypoints
    - cruise_speed_mps: nominal commanded airspeed
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
    wtype = str(wcfg.get("type", "sinusoidal")).strip().lower()

    if wtype in ("none", "no_wind", "zero"):
        wind = ZeroWind()

    elif wtype in ("uniform", "constant"):
        wind = UniformWind(
            w_enu_mps=np.array(
                [
                    float(wcfg.get("w_east_mps", 0.0)),
                    float(wcfg.get("w_north_mps", 0.0)),
                    float(wcfg.get("w_up_mps", 0.0)),
                ],
                dtype=float,
            )
        )

    elif wtype in ("vortex", "swirl"):
        wind = VortexFieldWind(
            mean_enu_mps=np.array(
                [
                    float(wcfg.get("mean_east_mps", 0.0)),
                    float(wcfg.get("mean_north_mps", 0.0)),
                    float(wcfg.get("mean_up_mps", 0.0)),
                ],
                dtype=float,
            ),
            center_xy_m=(float(wcfg.get("center_x_m", 0.0)), float(wcfg.get("center_y_m", 0.0))),
            swirl_strength=float(wcfg.get("swirl_strength", 1500.0)),
            core_radius_m=float(wcfg.get("core_radius_m", 250.0)),
            vertical_shear=float(wcfg.get("vertical_shear", 0.0)),
        )

    else:
        # default sinusoidal time-varying wind
        wind = SinusoidalWind(
            mean_enu_mps=np.array(
                [
                    float(wcfg.get("mean_east_mps", 2.0)),
                    float(wcfg.get("mean_north_mps", 0.0)),
                    float(wcfg.get("mean_up_mps", 0.0)),
                ],
                dtype=float,
            ),
            amp_enu_mps=np.array(
                [
                    float(wcfg.get("amp_east_mps", 1.0)),
                    float(wcfg.get("amp_north_mps", 1.0)),
                    float(wcfg.get("amp_up_mps", 0.0)),
                ],
                dtype=float,
            ),
            period_s=float(wcfg.get("period_s", 600.0)),
            phase_s=float(wcfg.get("phase_s", 0.0)),
        )

    # Optional: uncertainty wrapper for Monte-Carlo robustness
    if bool(wcfg.get("stochastic", False)):
        wind = StochasticWind(
            base=wind,
            sigma_bias_mps=float(wcfg.get("sigma_bias_mps", 1.0)),
            sigma_gust_mps=float(wcfg.get("sigma_gust_mps", 0.8)),
            tau_gust_s=float(wcfg.get("tau_gust_s", 60.0)),
            dt_s=float(vcfg.get("dt_s", 1.0)),
        )

    # --- Geofence map ---
    gcfg = cfg.get("geofence", {}) or {}
    zones_yaml = gcfg.get("no_fly_zones", []) or []
    zones: List[NoFlyZone] = []
    for z in zones_yaml:
        poly = [(float(p[0]), float(p[1])) for p in (z.get("polygon", []) or [])]
        if len(poly) >= 3:
            zones.append(NoFlyZone(zone_id=str(z.get("id", "NFZ")), polygon=poly))
    geofence = GeofenceMap(zones=zones) if zones else None
    clearance_m = float(gcfg.get("clearance_m", 0.0))

    # --- Initial state ---
    ic = cfg.get("initial_state", {}) or {}
    x_init = float(ic.get("x_m", 0.0))
    y_init = float(ic.get("y_m", 0.0))
    z_init = float(ic.get("z_m", 0.0))

    # --- Dynamics + sim engine ---
    dt_s = float(vcfg.get("dt_s", 1.0))
    bank_max_deg = float(vcfg.get("bank_max_deg", 30.0))
    climb_rate_max_mps = float(vcfg.get("climb_rate_max_mps", 3.0))
    descent_rate_max_mps = float(vcfg.get("descent_rate_max_mps", 3.0))

    dyn = DynParams(
        v_air_min_mps=min_v,
        v_air_max_mps=max_v,
        bank_max_rad=math.radians(bank_max_deg),
        yaw_rate_max_radps=(
            float(vcfg["yaw_rate_max_radps"]) if "yaw_rate_max_radps" in vcfg else None
        ),
        climb_rate_max_mps=climb_rate_max_mps,
        descent_rate_max_mps=descent_rate_max_mps,
        dt_s=dt_s,
        z_min_m=float(vcfg["z_min_m"]) if "z_min_m" in vcfg else None,
        z_max_m=float(vcfg["z_max_m"]) if "z_max_m" in vcfg else None,
    )

    simcfg = cfg.get("simulation", {}) or {}
    sim_params = AircraftSimParams(
        t_max_s=float(simcfg.get("t_max_s", 10_000.0)),
        reach_radius_m=float(vcfg.get("reach_radius_m", 15.0)),
        stall_time_s=float(simcfg.get("stall_time_s", 120.0)),
        stall_improve_m=float(simcfg.get("stall_improve_m", 1.0)),
        k_heading=float(simcfg.get("k_heading", 1.2)),
        k_speed=float(simcfg.get("k_speed", 0.8)),
        max_speed_step_mps=float(simcfg.get("max_speed_step_mps", 3.0)),
    )

    batt_cap = float(vcfg.get("battery_capacity_Wh", float(ic.get("battery_Wh", 800.0))))
    battery_params = BatteryParams(
        capacity_Wh=batt_cap,
        initial_Wh=float(ic.get("battery_Wh", batt_cap)),
        p_idle_W=float(vcfg.get("p_idle_W", 60.0)),
        k_v_W_per_m2s2=float(vcfg.get("k_v_W_per_m2s2", 1.0)),
        k_climb_W_per_mps=float(vcfg.get("k_climb_W_per_mps", 120.0)),
        k_turn_W_per_radps=float(vcfg.get("k_turn_W_per_radps", 30.0)),
    )

    sim_engine = AircraftSim(
        dyn=dyn,
        sim=sim_params,
        wind=wind,
        battery_params=battery_params,
        geofence=geofence,
        geofence_clearance_m=clearance_m,
    )

    # --- Build plan from decisions ---
    def build_plan(a: DecisionAssignment) -> Plan:
        order = list(a["visit_order"])
        cruise_speed = float(np.array(a["cruise_speed_mps"]).reshape(-1)[0])

        name_to_wp = {wp.name: wp for wp in mission.waypoints}
        ordered = [name_to_wp[n] for n in order]

        rows = [{"id": "START", "x_m": x_init, "y_m": y_init, "z_m": z_init, "eta_s": 0.0}]
        t_eta = 0.0
        x, y = x_init, y_init
        for wp in ordered:
            d = _dist2((x, y), (wp.x, wp.y))
            dt = d / max(1e-6, cruise_speed)
            t_eta += dt
            rows.append(
                {
                    "id": wp.name,
                    "x_m": float(wp.x),
                    "y_m": float(wp.y),
                    "z_m": float(wp.z),
                    "eta_s": float(t_eta),
                }
            )
            x, y = wp.x, wp.y

        return Plan(
            kind="aircraft",
            waypoints=rows,
            metadata={
                "mission_id": mission.mission_id,
                "cruise_speed_mps": float(cruise_speed),
                "heading_rad": float(ic.get("heading_rad", 0.0)),
                "speed_mps": float(ic.get("speed_mps", cruise_default)),
                "battery_Wh": float(ic.get("battery_Wh", batt_cap)),
            },
        )

    # --- Simulation wrapper ---
    def simulate(plan: Plan, rng: np.random.Generator | None) -> SimResult:
        return sim_engine.simulate(plan, rng=rng, t_max_s=float(sim_params.t_max_s))

    # --- Constraints ---
    constraints = _aircraft_constraints_from_cfg(cfg)

    # --- Objective ---
    obj_cfg = cfg.get("objective", {}) or {}
    terms_cfg = obj_cfg.get("terms", []) or []
    objective = Objective()

    if terms_cfg:
        for term in terms_cfg:
            tname = str(term.get("name", "")).strip().lower()
            weight = float(term.get("weight", 1.0))
            if tname in ("total_time", "time", "t_end_s"):
                objective.add(term_minimize_time(name="time", weight=weight, key="t_end_s"))
            elif tname in ("energy_used", "energy", "energy_used_wh"):
                objective.add(
                    term_minimize_energy(name="energy", weight=weight, key="energy_used_Wh")
                )
    else:
        # Default: minimize time (AeroHack objective option)
        objective.add(term_minimize_time(name="time", weight=1.0, key="t_end_s"))

    # --- Robustness wiring from YAML ---
    rob = cfg.get("robustness", {}) or {}
    robustness_cases = int(rob.get("cases", 0)) if rob else 0

    return Problem(
        decision_space=ds,
        build_plan=build_plan,
        simulate=simulate,
        constraints=constraints,
        objective=objective,
        robustness_cases=robustness_cases,
        metadata={"mission_id": mission.mission_id},
    )
