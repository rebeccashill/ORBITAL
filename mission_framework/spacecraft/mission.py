# mission_framework/spacecraft/mission.py
"""
7-day CubeSat-style mission definition (MODULE B / spacecraft).

Aligned with:
- mission_framework/core/types.py (Event, EventType, Schedule, Plan, SimResult, Trajectory)
- YAML keys:
    orbit.altitude_km, inclination_deg, raan_deg, true_anomaly_deg, duration_days, time_step_s, epoch_utc
    mission.targets
    top-level ground_stations
    spacecraft bus parameters (battery/power/slew proxies)

Planning-grade demo:
- Targets "visible" when elevation >= threshold (via visibility_core.py)
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
from mission_framework.core.types import Event, EventType, Plan, Schedule, SimResult, Trajectory
from mission_framework.spacecraft.attitude import (
    PointingTask,
    SlewConfig,
    sequence_feasibility_margin,
)
from mission_framework.spacecraft.constraints import default_spacecraft_constraints
from mission_framework.spacecraft.orbit_compat import (
    KeplerianElements,
    propagate_ecef_trajectory,
)
from mission_framework.spacecraft.power import (
    BatteryConfig,
    BatteryModel,
    PowerLoads,
    make_steps_from_schedule,
)
from mission_framework.spacecraft.visibility_core import GroundSite, compute_access_windows

R_EARTH_KM = 6378.137


def _compute_ops_per_orbit_max(events: List[Event], orbit_period_s: float) -> int:
    """
    Return the maximum number of "ops" (OBS+DL) that occur in any orbit-length bucket.
    Simple proxy for ops-per-orbit constraints.
    """
    if orbit_period_s <= 0:
        return 0
    ops_times = [
        float(e.t_start) for e in events if e.etype in (EventType.OBSERVATION, EventType.DOWNLINK)
    ]
    if not ops_times:
        return 0

    # Bucket by orbit index
    buckets: Dict[int, int] = {}
    for t in ops_times:
        k = int(np.floor(t / orbit_period_s))
        buckets[k] = buckets.get(k, 0) + 1
    return int(max(buckets.values()))


def _compute_cooldown_violation_s(events: List[Event]) -> float:
    """
    Sum cooldown violations across observations.
    Uses per-observation cooldown_s stored in event.data (or 0 if absent).
    """
    obs = [e for e in events if e.etype == EventType.OBSERVATION]
    if len(obs) < 2:
        return 0.0
    obs.sort(key=lambda e: e.t_start)

    total_violation = 0.0
    for i in range(1, len(obs)):
        prev = obs[i - 1]
        cur = obs[i]
        cooldown = float(prev.data.get("cooldown_s", 0.0))
        required_start = float(prev.t_end) + cooldown
        if float(cur.t_start) < required_start:
            total_violation += required_start - float(cur.t_start)
    return float(total_violation)


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
    time_windows: Tuple[
        Dict[str, Any], ...
    ] = ()  # stored as provided (UTC strings), not enforced yet


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
    Accepts YAML orbit fields:
      altitude_km, inclination_deg, raan_deg, true_anomaly_deg, epoch_utc
    Produces KeplerianElements used by orbit_compat.py.
    """
    o = cfg.get("orbit", {}) or {}

    alt_km = float(o.get("altitude_km", 550.0))
    a_km = float(R_EARTH_KM + alt_km)  # circular-ish SMA proxy
    e = float(o.get("e", 0.001))

    i_rad = _deg2rad(float(o.get("inclination_deg", 97.6)))
    raan_rad = _deg2rad(float(o.get("raan_deg", 0.0)))
    argp_rad = _deg2rad(float(o.get("argp_deg", 0.0)))  # optional

    # YAML gives true anomaly; for demo, treat as mean anomaly seed
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
    t_horizon = _horizon_seconds(cfg)

    # -------------------------
    # Targets
    # -------------------------
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
                obs_duration_s=float(t.get("obs_duration_s", 30.0)),
                cooldown_s=float(t.get("cooldown_s", 0.0)),
                time_windows=tuple((t.get("time_windows", []) or [])),
            )
        )

    # -------------------------
    # Ground stations (top-level YAML key)
    # -------------------------
    gs_list = cfg.get("ground_stations", []) or []
    if not gs_list:
        raise ValueError("spacecraft scenario requires top-level ground_stations")

    stations: List[GroundSite] = []
    for gs in gs_list:
        stations.append(
            GroundSite.from_km(
                site_id=str(gs.get("id", "")),
                name=str(gs.get("name", "")),  # optional; defaults to site_id in from_km if blank
                lat_deg=float(gs.get("lat_deg")),
                lon_deg=float(gs.get("lon_deg")),
                alt_km=float(gs.get("alt_km", 0.0)),
                min_elev_deg=float(gs.get("min_elevation_deg", 10.0)),
            )
        )

    # -------------------------
    # Visibility precompute
    # -------------------------
    step_s = float((cfg.get("orbit", {}) or {}).get("time_step_s", 30.0))
    default_min_el = 10.0

    # Propagate once (ECEF positions)
    t_arr, r_ecef_arr = propagate_ecef_trajectory(el, 0.0, t_horizon, step_s)

    # Station access windows
    station_windows: Dict[str, List[Tuple[float, float]]] = {}
    for s in stations:
        # compute_access_windows keys by site.name (strict core behavior)
        wins_dict = compute_access_windows(t=t_arr, r_ecef=r_ecef_arr, sites=[s])
        station_windows[s.name] = wins_dict.get(s.name, [])

    # Target access windows: treat targets as pseudo-sites
    target_windows: Dict[str, List[Tuple[float, float]]] = {}
    for tgt in targets:
        pseudo = GroundSite.from_km(
            site_id=str(tgt.target_id),
            name=str(tgt.target_id),
            lat_deg=float(tgt.lat_deg),
            lon_deg=float(tgt.lon_deg),
            alt_km=0.0,
            min_elev_deg=default_min_el,
        )
        wins_dict = compute_access_windows(t=t_arr, r_ecef=r_ecef_arr, sites=[pseudo])
        target_windows[tgt.target_id] = wins_dict.get(pseudo.name, [])

    # -------------------------
    # Decision space
    # -------------------------
    target_ids = [t.target_id for t in targets]

    ds = DecisionSpace(
        variables=[
            *[DiscreteVar(f"select_{tid}", items=[0, 1]) for tid in target_ids],
            *[ContinuousVar(f"obs_offset_{tid}", bounds=Bounds(0.0, 1.0)) for tid in target_ids],
            DiscreteVar("downlink_policy", items=[0, 1, 2]),
        ]
    )

    # -------------------------
    # Build plan from assignment
    # -------------------------
    def build_plan(a: DecisionAssignment) -> Plan:
        events: List[Event] = []

        # Observations (demo: first available visibility window)
        for tgt in targets:
            sel = int(a[f"select_{tgt.target_id}"])
            if sel <= 0:
                continue

            wins = target_windows.get(tgt.target_id, [])
            if not wins:
                continue

            w0, w1 = wins[0]
            offset = float(np.array(a[f"obs_offset_{tgt.target_id}"]).reshape(-1)[0])
            start = float(w0 + offset * max(0.0, (w1 - w0) - tgt.obs_duration_s))
            end = float(start + tgt.obs_duration_s)

            events.append(
                Event(
                    t_start=start,
                    t_end=end,
                    etype=EventType.OBSERVATION,
                    label=f"OBS_{tgt.target_id}",
                    target_id=tgt.target_id,
                    location=(float(tgt.lat_deg), float(tgt.lon_deg)),
                    data={
                        "value": float(tgt.value),
                        "duration_s": float(tgt.obs_duration_s),
                        "cooldown_s": float(tgt.cooldown_s),
                    },
                )
            )

        # Downlinks (simple policy controlling where inside each access window we place the downlink)
        policy = int(a["downlink_policy"])
        frac = 0.2 if policy == 0 else (0.5 if policy == 1 else 0.8)

        dl_dur = 180.0  # proxy duration
        max_dl_windows = int((cfg.get("downlink", {}) or {}).get("max_windows_per_station", 6))

        for station_name, wins in station_windows.items():
            wins = list(wins)[:max_dl_windows]
            for w0, w1 in wins:
                if (w1 - w0) < dl_dur:
                    continue

                start = float(w0 + frac * ((w1 - w0) - dl_dur))
                end = float(start + dl_dur)

                st = next((s for s in stations if s.name == station_name), None)
                loc = (float(st.lat_deg), float(st.lon_deg)) if st is not None else None

                events.append(
                    Event(
                        t_start=start,
                        t_end=end,
                        etype=EventType.DOWNLINK,
                        label=f"DL_{station_name}",
                        target_id=None,
                        location=loc,
                        data={"station_id": station_name, "duration_s": float(dl_dur)},
                    )
                )

        events.sort(key=lambda e: e.t_start)
        sched = Schedule(events=events, metadata={"horizon_s": float(t_horizon)})

        return Plan(
            kind="spacecraft",
            schedule=sched,
            metadata={
                "scenario": scenario.get("name", "spacecraft_demo"),
                "horizon_s": float(t_horizon),
            },
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
                station_name = str(e.data.get("station_id", ""))
                st = next((s for s in stations if s.name == station_name), None)
                if st is None:
                    continue
                d = _ecef_direction_to_site(st.lat_deg, st.lon_deg)

            else:
                continue

            tasks.append(
                PointingTask(
                    t_start=float(e.t_start),
                    t_end=float(e.t_end),
                    direction_ecef=d,
                    label=str(e.label),
                )
            )

        tasks.sort(key=lambda t: t.t_start)
        slew_margin_s = sequence_feasibility_margin(tasks, cfg=slew_cfg)

        # Power proxy
        power_cfg = cfg.get("power", {}) or {}
        min_Wh = float(power_cfg.get("min_Wh", 0.0))
        bcfg = BatteryConfig(
            capacity_Wh=float(sc.get("battery_capacity_Wh", 120.0)),
            initial_Wh=float(sc.get("initial_battery_Wh", 100.0)),
            charge_power_W=float(sc.get("charge_rate_W", 35.0)),
            charge_eff=0.95,
            discharge_eff=1.0,
            min_Wh=min_Wh,
        )
        loads = PowerLoads(
            bus_W=float(sc.get("base_load_W", 20.0)),
            payload_obs_W=float(sc.get("payload_power_W", 40.0)),
            radio_downlink_W=float(sc.get("downlink_power_W", 30.0)),
            slew_W=10.0,
        )

        # Simple sunlight proxy
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
        steps = make_steps_from_schedule(
            simple_events, sunlight_fn=sunlight_fn, default_in_sun=True
        )

        batt_model = BatteryModel(bcfg, loads=loads)
        trace = batt_model.simulate(
            steps,
            dt_internal_s=float((cfg.get("orbit", {}) or {}).get("time_step_s", 30.0)),
        )

        # Delivered value proxy: observation counts only if any downlink occurs after it
        dl_times = sorted(float(e.t_start) for e in events if e.etype == EventType.DOWNLINK)

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
            frame="time",
            metadata={"dummy": True},
        )

        ops_cfg = cfg.get("ops", {}) or {}
        orbit_period_s = float(ops_cfg.get("orbit_period_s", 5400.0))

        ops_per_orbit_max = _compute_ops_per_orbit_max(events, orbit_period_s=orbit_period_s)
        cooldown_violation_s = _compute_cooldown_violation_s(events)

        return SimResult(
            t=(
                trace.t_s
                if getattr(trace, "t_s", np.array([])).size
                else np.array([0.0], dtype=float)
            ),
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
                "ops_per_orbit_max": float(ops_per_orbit_max),
                "cooldown_violation_s": float(cooldown_violation_s),
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
