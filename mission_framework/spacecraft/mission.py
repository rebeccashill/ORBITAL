# mission_framework/spacecraft/mission.py
"""
7-day CubeSat-style mission definition (MODULE B / spacecraft).

This file is aligned with:
- mission_framework/core/types.py (Event, EventType, Schedule, Plan, SimResult)
and with your YAML:
- orbit.altitude_km, inclination_deg, raan_deg, true_anomaly_deg, duration_days, time_step_s
- mission.targets (with optional time_windows in UTC strings; stored but not enforced yet)
- top-level ground_stations
- spacecraft bus parameters (battery/power/slew/proxies)

Planning-grade demo:
- Targets visible when elevation >= threshold (proxy via visibility.py)
- Downlinks scheduled during ground station access windows
- Battery proxy (charge/discharge) + slew feasibility proxy
- Objective: maximize delivered mission_value
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mission_framework.core.decision_variables import (
    Bounds,
    ContinuousVar,
    DecisionAssignment,
    DecisionSpace,
    DiscreteVar,
)
from mission_framework.core.objective import Objective, term_maximize_value
from mission_framework.core.planner import Problem
from mission_framework.core.types import Plan, Schedule, Event, EventType, SimResult, Trajectory

from mission_framework.spacecraft.orbit import KeplerianElements, OrbitConfig, R_EARTH_KM, propagate_ecef_trajectory
from mission_framework.spacecraft.visibility import GroundSite, compute_access_windows
from mission_framework.spacecraft.attitude import SlewConfig, PointingTask, sequence_feasibility_margin
from mission_framework.spacecraft.power import BatteryConfig, PowerLoads, BatteryModel, make_steps_from_schedule
from mission_framework.spacecraft.constraints import default_spacecraft_constraints


# ============================================================
# Data models
# ============================================================

@dataclass(frozen=True)
class GroundTarget:
    target_id: str
    lat_deg: float
    lon_deg: float
    value: float = 1.0
    obs_duration_s: float = 30.0
    cooldown_s: float = 0.0
    time_windows: Tuple[Dict[str, Any], ...] = ()  # store as provided (UTC strings)


def _deg2rad(d: float) -> float:
    import math
    return float(math.radians(float(d)))


def _ecef_direction_to_site(lat_deg: float, lon_deg: float) -> np.ndarray:
    """
    Simplified pointing direction vector:
    unit vector from Earth center to that lat/lon (ECEF-ish).
    """
    import math
    lat = _deg2rad(lat_deg)
    lon = _deg2rad(lon_deg)
    cl = math.cos(lat)
    return np.array([cl * math.cos(lon), cl * math.sin(lon), math.sin(lat)], dtype=float)


def _parse_kepler_from_yaml(cfg: Dict[str, Any]) -> KeplerianElements:
    """
    Accepts your YAML orbit fields:
      altitude_km, inclination_deg, raan_deg, true_anomaly_deg, epoch_utc
    Produces KeplerianElements used by orbit.py.
    """
    o = cfg.get("orbit", {}) or {}

    alt_km = float(o.get("altitude_km", 550.0))
    a_km = float(R_EARTH_KM + alt_km)  # circular-ish
    e = float(o.get("e", 0.001))

    i_rad = _deg2rad(float(o.get("inclination_deg", 97.6)))
    raan_rad = _deg2rad(float(o.get("raan_deg", 0.0)))
    argp_rad = _deg2rad(float(o.get("argp_deg", 0.0)))  # not present in YAML, default 0

    # YAML gives "true_anomaly_deg" not mean anomaly; good enough for demo -> treat as M0
    M0_rad = _deg2rad(float(o.get("true_anomaly_deg", 0.0)))

    epoch_utc = str(o.get("epoch_utc", "2026-01-01T00:00:00Z"))

    return KeplerianElements(
        a_km=a_km,
        e=e,
        i_rad=i_rad,
        raan_rad=raan_rad,
        argp_rad=argp_rad,
        M0_rad=M0_rad,
        epoch_utc=epoch_utc,
    )


def _horizon_seconds(cfg: Dict[str, Any]) -> float:
    o = cfg.get("orbit", {}) or {}
    days = float(o.get("duration_days", (cfg.get("mission", {}) or {}).get("horizon_days", 7.0)))
    return float(days * 24.0 * 3600.0)


# ============================================================
# Problem builder
# ============================================================

def build_problem_from_config(cfg: Dict[str, Any]) -> Problem:
    scenario = cfg.get("scenario", {}) or {}
    if str(scenario.get("type", "")).strip().lower() != "spacecraft":
        raise ValueError("build_problem_from_config called with non-spacecraft scenario")

    el = _parse_kepler_from_yaml(cfg)
    ocfg = OrbitConfig()
    t_horizon = _horizon_seconds(cfg)

    # Targets
    mission_cfg = cfg.get("mission", {}) or {}
    tlist = mission_cfg.get("targets", []) or []
    if not tlist:
        raise ValueError("spacecraft scenario requires mission.targets")

    targets: List[GroundTarget] = []
    for t in tlist:
        targets.append(
            GroundTarget(
                target_id=str(t.get("id", "")),
                lat_deg=float(t.get("lat_deg")),
                lon_deg=float(t.get("lon_deg")),
                value=float(t.get("value", 1.0)),
                # your YAML doesn't provide obs duration; default to 30s
                obs_duration_s=float(t.get("obs_duration_s", 30.0)),
                cooldown_s=float(t.get("cooldown_s", 0.0)),
                time_windows=tuple((t.get("time_windows", []) or [])),
            )
        )

    # Ground stations (YOUR YAML: top-level key)
    gs_list = cfg.get("ground_stations", []) or []
    if not gs_list:
        raise ValueError("spacecraft scenario requires top-level ground_stations")

    stations: List[GroundSite] = []
    for gs in gs_list:
        stations.append(
            GroundSite(
                site_id=str(gs.get("id", "")),
                lat_deg=float(gs.get("lat_deg")),
                lon_deg=float(gs.get("lon_deg")),
                alt_km=float(gs.get("alt_km", 0.0)),
            )
        )

    # Visibility settings (use station min_elevation if present, else default)
    step_s = float((cfg.get("orbit", {}) or {}).get("time_step_s", 30.0))
    default_min_el = 10.0

    # Precompute orbit trajectory once (used for all visibility checks below)
    t_arr, r_ecef_arr = propagate_ecef_trajectory(el, 0.0, t_horizon, step_s)

    # Precompute contact windows for stations
    station_windows: Dict[str, List[Tuple[float, float]]] = {}
    for s in stations:
        gs_yaml = next((g for g in gs_list if str(g.get("id", "")) == s.site_id), {})
        min_el_deg = float(gs_yaml.get("min_elevation_deg", default_min_el))

        wins_dict = compute_access_windows(
            t=t_arr,
            r_ecef=r_ecef_arr,
            sites=[s],
            min_elevation_deg=min_el_deg,
        )
        site_key = str(s.site_id or s.name or "GS")
        station_windows[s.site_id] = wins_dict.get(site_key, [])

    # Precompute target visibility windows (treat target as a ground site)
    target_windows: Dict[str, List[Tuple[float, float]]] = {}
    for t in targets:
        pseudo = GroundSite(site_id=t.target_id, lat_deg=t.lat_deg, lon_deg=t.lon_deg, alt_km=0.0)
        wins_dict = compute_access_windows(
            t=t_arr,
            r_ecef=r_ecef_arr,
            sites=[pseudo],
            min_elevation_deg=default_min_el,
        )
        target_key = str(t.target_id)
        target_windows[t.target_id] = wins_dict.get(target_key, [])

    # -------------------------
    # Decision space
    # -------------------------
    target_ids = [t.target_id for t in targets]

    ds = DecisionSpace(variables=[
        *[DiscreteVar(f"select_{tid}", items=[0, 1]) for tid in target_ids],
        *[ContinuousVar(f"obs_offset_{tid}", bounds=Bounds(0.0, 1.0)) for tid in target_ids],
        DiscreteVar("downlink_policy", items=[0, 1, 2]),
    ])

    # -------------------------
    # Build plan from assignment
    # -------------------------
    def build_plan(a: DecisionAssignment) -> Plan:
        events: List[Event] = []

        # Observations (use first available visibility window, simple demo)
        for t in targets:
            sel = int(a[f"select_{t.target_id}"])
            if sel <= 0:
                continue

            wins = target_windows.get(t.target_id, [])
            if not wins:
                continue

            w0, w1 = wins[0]
            offset = float(np.array(a[f"obs_offset_{t.target_id}"]).reshape(-1)[0])
            start = float(w0 + offset * max(0.0, (w1 - w0) - t.obs_duration_s))
            end = float(start + t.obs_duration_s)

            events.append(Event(
                t_start=start,
                t_end=end,
                etype=EventType.OBSERVATION,
                label=f"OBS_{t.target_id}",
                target_id=t.target_id,
                location=(float(t.lat_deg), float(t.lon_deg)),
                data={"value": float(t.value), "duration_s": float(t.obs_duration_s)},
            ))

        # Downlinks
        policy = int(a["downlink_policy"])
        frac = 0.2 if policy == 0 else (0.5 if policy == 1 else 0.8)

        # Use downlink duration proxy from YAML spacecraft.data_rate... later; for now fixed duration
        dl_dur = 180.0

        max_dl_windows = int((cfg.get("downlink", {}) or {}).get("max_windows_per_station", 6))

        for sid, wins in station_windows.items():
            wins = list(wins)[:max_dl_windows]
            for (w0, w1) in wins:
                if (w1 - w0) < dl_dur:
                    continue
                start = float(w0 + frac * ((w1 - w0) - dl_dur))
                end = float(start + dl_dur)

                st = next((s for s in stations if s.site_id == sid), None)
                loc = (float(st.lat_deg), float(st.lon_deg)) if st is not None else None

                events.append(Event(
                    t_start=start,
                    t_end=end,
                    etype=EventType.DOWNLINK,
                    label=f"DL_{sid}",
                    target_id=None,
                    location=loc,
                    data={"station_id": sid, "duration_s": float(dl_dur)},
                ))

        events.sort(key=lambda e: e.t_start)
        sched = Schedule(events=events, metadata={"horizon_s": float(t_horizon)})

        return Plan(
            kind="spacecraft",
            schedule=sched,
            metadata={"scenario": scenario.get("name", "spacecraft_demo"), "horizon_s": float(t_horizon)},
        )

    # -------------------------
    # Simulate schedule -> SimResult
    # -------------------------
    def simulate(plan: Plan, rng: Optional[np.random.Generator]) -> SimResult:
        sched = plan.schedule or Schedule()
        events = list(sched.events)

        sc = cfg.get("spacecraft", {}) or {}

        # Slew feasibility proxy
        slew_cfg = SlewConfig(
            max_slew_rate_deg_s=float(sc.get("max_slew_rate_deg_per_s", 1.0)),
            settle_time_s=2.0,
        )

        tasks: List[PointingTask] = []
        for e in events:
            if e.etype == EventType.OBSERVATION:
                if e.location is None:
                    continue
                lat_deg, lon_deg = float(e.location[0]), float(e.location[1])
                d = _ecef_direction_to_site(lat_deg, lon_deg)
            elif e.etype == EventType.DOWNLINK:
                sid = str(e.data.get("station_id", ""))
                st = next((s for s in stations if s.site_id == sid), None)
                if st is None:
                    continue
                d = _ecef_direction_to_site(st.lat_deg, st.lon_deg)
            else:
                continue

            tasks.append(PointingTask(
                t_start=float(e.t_start),
                t_end=float(e.t_end),
                direction_ecef=d,
                label=str(e.label),
            ))

        tasks.sort(key=lambda t: t.t_start)
        slew_margin_s = sequence_feasibility_margin(tasks, cfg=slew_cfg)

        # Power proxy from YAML spacecraft block
        bcfg = BatteryConfig(
            capacity_Wh=float(sc.get("battery_capacity_Wh", 120.0)),
            initial_Wh=float(sc.get("initial_battery_Wh", 100.0)),
            charge_power_W=float(sc.get("charge_rate_W", 35.0)),
            charge_eff=0.95,
            discharge_eff=1.0,
            min_Wh=0.0,
        )
        loads = PowerLoads(
            bus_W=float(sc.get("base_load_W", 20.0)),
            payload_obs_W=float(sc.get("payload_power_W", 40.0)),
            radio_downlink_W=float(sc.get("downlink_power_W", 30.0)),
            slew_W=10.0,
        )

        # simple sunlight proxy
        sun_frac = 0.6

        def sunlight_fn(tmid: float) -> bool:
            period = 5400.0
            phase = (tmid % period) / period
            return phase < sun_frac

        def mode_for_event(e: Event) -> str:
            if e.etype == EventType.OBSERVATION:
                return "observe"
            if e.etype == EventType.DOWNLINK:
                return "downlink"
            if e.etype == EventType.SLEW:
                return "slew"
            return "idle"

        simple_events = [(float(e.t_start), float(e.t_end), mode_for_event(e)) for e in events]
        steps = make_steps_from_schedule(simple_events, sunlight_fn=sunlight_fn, default_in_sun=True)

        batt_model = BatteryModel(bcfg, loads=loads)
        trace = batt_model.simulate(steps, dt_internal_s=float((cfg.get("orbit", {}) or {}).get("time_step_s", 30.0)))

        # Delivered value proxy: observation counts only if any downlink occurs after it
        dl_times = [float(e.t_start) for e in events if e.etype == EventType.DOWNLINK]
        dl_times.sort()

        delivered_value = 0.0
        obs_scheduled = 0
        obs_delivered = 0
        for e in events:
            if e.etype != EventType.OBSERVATION:
                continue
            obs_scheduled += 1
            val = float(e.data.get("value", 0.0))
            if any(tdl >= float(e.t_end) for tdl in dl_times):
                delivered_value += val
                obs_delivered += 1

        horizon = float(plan.metadata.get("horizon_s", 0.0))
        dummy_traj = Trajectory(
            t=np.array([0.0, horizon], dtype=float),
            state=np.zeros((2, 1), dtype=float),
            control=None,
            frame="time",
            metadata={"dummy": True},
        )

        return SimResult(
            t=trace.t_s if trace.t_s.size else np.array([0.0], dtype=float),
            trajectory=dummy_traj,
            schedule=sched,
            resources={"battery_Wh": trace.battery_Wh, "net_power_W": trace.net_power_W},
            scalars={
                "mission_value": float(delivered_value),
                "obs_scheduled": float(obs_scheduled),
                "obs_delivered": float(obs_delivered),
                "slew_margin_s": float(slew_margin_s),
                "min_battery_Wh": float(trace.min_battery_Wh()),
                "final_battery_Wh": float(trace.final_battery_Wh()),
            },
            metadata={
                "station_windows": station_windows,
                "target_windows": target_windows,
                "targets_time_windows_utc": {t.target_id: list(t.time_windows) for t in targets},
            },
        )

    constraints = default_spacecraft_constraints(cfg=cfg)
    objective = Objective().add(term_maximize_value(name="value", weight=1.0, key="mission_value"))

    # Explicitly cast constraints to the correct type
    from typing import cast
    from mission_framework.core.constraints import Constraint, ConstraintGroup

    return Problem(
        decision_space=ds,
        build_plan=build_plan,
        simulate=simulate,
        constraints=cast(list[Constraint | ConstraintGroup], constraints),
        objective=objective,
        robustness_cases=int((cfg.get("robustness", {}) or {}).get("cases", 0)),
        metadata={"domain": "spacecraft"},
    )