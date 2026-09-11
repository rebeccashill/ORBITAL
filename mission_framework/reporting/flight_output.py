# mission_framework/reporting/flight_output.py
"""
Flight path / waypoint output utilities (Aircraft Module A).

Exports:
- Ordered waypoints with timestamps (ETA)
- Optional time series trajectory (if available)
- Minimal JSON/CSV-friendly dictionaries

This module is intentionally lightweight and does not enforce a specific internal format.
It expects:
- Plan.kind == "aircraft"
- Plan.waypoints: list of dicts (each dict may include x/y/z or lat/lon/alt, plus eta/t)
- SimResult.trajectory optionally contains time series state history

Reporting guidance:
- Keep exports simple and readable.
- Pair flight plan tables with constraint reports and summary metrics.
"""

from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from mission_framework.core.decision_variables import MutationConfig
from mission_framework.core.json_utils import strict_json_dumps, write_strict_json
from mission_framework.core.objective import ScoreConfig
from mission_framework.core.planner import Planner, PlannerConfig
from mission_framework.core.types import Plan, SimResult, Trajectory


def flight_plan_table(plan: Plan) -> List[Dict[str, Any]]:
    """
    Return a list of rows for the waypoint plan.

    Expected waypoint dict keys (flexible):
      - id (string)
      - x_m, y_m, z_m OR lat_deg, lon_deg, alt_m
      - eta_s or t_s or time_utc
    """
    if plan.kind != "aircraft":
        raise ValueError(f"flight_plan_table expects plan.kind='aircraft', got '{plan.kind}'")

    wps = plan.waypoints or []
    rows: List[Dict[str, Any]] = []

    for i, wp in enumerate(wps):
        row = {"seq": i}
        row.update(wp)
        # normalize common time key
        if "eta_s" not in row:
            if "t_s" in row:
                row["eta_s"] = row["t_s"]
            elif "time_s" in row:
                row["eta_s"] = row["time_s"]
        rows.append(row)

    return rows


def trajectory_export(sim: SimResult, state_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Export trajectory time series (if present) into a JSON-friendly dict.

    state_names: optional list of names for state columns (length D).
    """
    if sim.trajectory is None:
        return {"present": False}

    traj: Trajectory = sim.trajectory
    t = np.asarray(traj.t, dtype=float)
    x = np.asarray(traj.state, dtype=float)

    out: Dict[str, Any] = {
        "present": True,
        "frame": traj.frame,
        "t_s": t.tolist(),
        "state": x.tolist(),
        "state_names": state_names,
        "metadata": dict(traj.metadata),
    }
    if traj.control is not None:
        out["control"] = np.asarray(traj.control, dtype=float).tolist()
    return out


def export_flight_json(
    plan: Plan,
    sim: Optional[SimResult] = None,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Create (and optionally write) a JSON export containing:
    - waypoint plan table
    - optional trajectory data
    - optional resource traces + scalars

    Returns the payload dict even if out_path is provided.
    """
    payload: Dict[str, Any] = {
        "kind": plan.kind,
        "waypoints": flight_plan_table(plan),
        "plan_metadata": dict(plan.metadata),
    }

    if sim is not None:
        payload["trajectory"] = trajectory_export(sim)
        payload["resources"] = {
            k: np.asarray(v, dtype=float).tolist() for k, v in sim.resources.items()
        }
        payload["scalars"] = dict(sim.scalars)
        payload["sim_metadata"] = dict(sim.metadata)

    if out_path is not None:
        write_strict_json(out_path, payload)

    return payload


def export_waypoints_csv(plan: Plan, out_path: Path) -> None:
    """
    Export waypoint plan as a CSV (human-friendly table).
    """
    rows = flight_plan_table(plan)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect union of keys for header
    keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _scalar(sim: Optional[SimResult], key: str, default: Optional[float] = None) -> Optional[float]:
    if sim is None:
        return default
    if key in sim.scalars:
        return float(sim.scalars[key])
    if key in sim.resources:
        values = np.asarray(sim.resources[key], dtype=float).reshape(-1)
        if values.size:
            return float(values[-1])
    return default


def _fmt_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(number):
        return "n/a"
    suffix = f" {unit}" if unit else ""
    if 0.0 < abs(number) < 1.0:
        return f"{number:.3g}{suffix}"
    return f"{number:.1f}{suffix}"


def _constraint_label(name: str) -> str:
    labels = {
        "all_waypoints_reached": "inspection_completion",
        "battery_nonnegative": "battery_nonnegative",
        "battery_reserve": "battery_reserve",
        "bank_angle_turn_limit": "turn_limit",
        "geofence_no_entry": "geofence_no_entry",
        "geofence_clearance": "geofence_clearance",
    }
    return labels.get(name, name)


def _constraint_by_name(constraints: Any, name: str) -> Optional[Any]:
    if hasattr(constraints, "by_name"):
        return constraints.by_name().get(name)
    for result in getattr(constraints, "results", []) or []:
        if str(getattr(result, "name", "")) == name:
            return result
    return None


def _hard_constraints(constraints: Any) -> Iterable[Any]:
    results = list(getattr(constraints, "results", []) or [])
    return [
        result
        for result in results
        if str(getattr(getattr(result, "severity", ""), "value", result.severity)) == "hard"
    ]


def _recommended_actions(constraints: Any) -> List[str]:
    hard = list(_hard_constraints(constraints))
    failed_names = [str(result.name) for result in hard if not bool(result.is_satisfied)]
    actions: List[str] = []

    if not failed_names:
        actions.append(
            "Proceed if the pilot-in-command confirms airspace authorization, crew readiness, "
            "and field conditions."
        )
        low_reserve = next((r for r in hard if str(r.name) == "battery_reserve"), None)
        if low_reserve is not None and float(low_reserve.min_margin) < 75.0:
            actions.append("Reduce route length or plan a relaunch / battery swap to widen reserve.")
        actions.append("Wait for better wind if observed conditions exceed the scenario model.")
        actions.append("Maintain the modeled geofence clearance before export to any flight system.")
        return actions

    if any("battery" in name for name in failed_names):
        actions.append("Reduce route length or plan a relaunch / battery swap.")
    if any("geofence" in name for name in failed_names):
        actions.append("Adjust geofence clearance or reroute the inspection corridor.")
    if "all_waypoints_reached" in failed_names:
        actions.append("Reduce the route or split the inspection into shorter sorties.")
    if "bank_angle_turn_limit" in failed_names:
        actions.append("Lower cruise speed or increase turn spacing.")
    actions.append("Wait for better wind before retrying if winds are the binding constraint.")
    return actions


def _resource_values(sim: SimResult, key: str) -> np.ndarray:
    return np.asarray(sim.resources.get(key, []), dtype=float).reshape(-1)


def _max_horizontal_wind_mps(sim: SimResult) -> Optional[float]:
    east = _resource_values(sim, "wind_east_mps")
    north = _resource_values(sim, "wind_north_mps")
    if east.size == 0 or north.size == 0:
        return None
    n = min(east.size, north.size)
    return float(np.max(np.hypot(east[:n], north[:n])))


def _status_from_margin(margin: Optional[float], warning_margin: float) -> str:
    if margin is None:
        return "unknown"
    if margin < 0.0:
        return "fail"
    if margin < warning_margin:
        return "warning"
    return "pass"


def _risk_points(margin: Optional[float], warning_margin: float) -> float:
    warn = max(float(warning_margin), 1e-6)
    if margin is None:
        return 50.0
    if margin < 0.0:
        return float(min(100.0, 80.0 + min(20.0, abs(float(margin)) / warn * 20.0)))
    if margin < warn:
        return float(40.0 + (warn - float(margin)) / warn * 30.0)
    return float(max(0.0, 30.0 * (1.0 - min(float(margin) / (3.0 * warn), 1.0))))


def _check(
    *,
    check_id: str,
    label: str,
    margin: Optional[float],
    unit: str,
    warning_margin: float,
    observed: Dict[str, Any],
    recommendation: str,
) -> Dict[str, Any]:
    points = _risk_points(margin, warning_margin)
    return {
        "id": check_id,
        "label": label,
        "status": _status_from_margin(margin, warning_margin),
        "margin": {"value": margin, "unit": unit},
        "warning_margin": {"value": float(warning_margin), "unit": unit},
        "risk_points": float(points),
        "observed": observed,
        "recommendation": recommendation,
    }


def _named_margin(constraints: Any, name: str) -> Optional[float]:
    result = _constraint_by_name(constraints, name)
    if result is None:
        return None
    return float(result.min_margin)


def build_inspection_constraint_audit(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a drone-inspection-specific audit payload from a solved aircraft mission."""
    cfg = cfg or {}
    vehicle = cfg.get("vehicle", {}) or {}
    wind_cfg = cfg.get("wind", {}) or {}
    geofence_cfg = cfg.get("geofence", {}) or {}

    reserve_wh = float(vehicle.get("battery_reserve_Wh", 0.0))
    battery_warning_wh = max(50.0, reserve_wh * 0.10) if reserve_wh > 0.0 else 50.0
    final_battery = _scalar(sim, "final_battery_Wh")
    battery_margin = _named_margin(constraints, "battery_reserve")
    if battery_margin is None and final_battery is not None and reserve_wh > 0.0:
        battery_margin = final_battery - reserve_wh

    max_speed = float(vehicle.get("max_speed_mps", 30.0))
    max_safe_wind = float(wind_cfg.get("max_safe_wind_mps", max(8.0, max_speed * 0.35)))
    wind_warning_mps = float(wind_cfg.get("warning_margin_mps", 2.0))
    max_wind = _max_horizontal_wind_mps(sim)
    wind_margin = None if max_wind is None else max_safe_wind - max_wind

    required_clearance = float(geofence_cfg.get("clearance_m", 0.0))
    geofence_margin = _named_margin(constraints, "geofence_clearance")
    geofence_warning_m = max(25.0, required_clearance * 0.25)
    no_entry_margin = _named_margin(constraints, "geofence_no_entry")
    if no_entry_margin is not None and no_entry_margin < 0.0:
        geofence_margin = min(geofence_margin or 0.0, no_entry_margin)

    completed = float(sim.scalars.get("waypoints_completed", 0.0))
    total = float(sim.scalars.get("waypoints_total", 0.0))
    missing = max(0.0, total - completed)
    route_margin = 1.0 if bool(sim.metadata.get("reached_all", False)) else -missing

    turn_margin = _named_margin(constraints, "bank_angle_turn_limit")
    turn_warning = float(vehicle.get("turn_warning_margin_radps", 0.05))

    checks = [
        _check(
            check_id="battery_reserve",
            label="Battery reserve margin",
            margin=battery_margin,
            unit="Wh",
            warning_margin=battery_warning_wh,
            observed={
                "final_battery_Wh": final_battery,
                "required_reserve_Wh": reserve_wh if reserve_wh > 0.0 else None,
            },
            recommendation="Reduce route length or plan a relaunch / battery swap.",
        ),
        _check(
            check_id="wind_weather",
            label="Wind / weather margin",
            margin=wind_margin,
            unit="m/s",
            warning_margin=wind_warning_mps,
            observed={
                "max_horizontal_wind_mps": max_wind,
                "max_safe_wind_mps": max_safe_wind,
            },
            recommendation="Wait for better wind or lower mission scope.",
        ),
        _check(
            check_id="geofence_clearance",
            label="Geofence / no-fly-zone clearance",
            margin=geofence_margin,
            unit="m",
            warning_margin=geofence_warning_m,
            observed={
                "required_clearance_m": required_clearance,
                "min_clearance_m": sim.scalars.get("geofence_min_clearance_m"),
                "geofence_violated": bool(sim.scalars.get("geofence_violated", 0.0)),
            },
            recommendation="Adjust route geometry or increase no-fly-zone clearance.",
        ),
        _check(
            check_id="route_completion",
            label="Route completion status",
            margin=route_margin,
            unit="completion",
            warning_margin=0.5,
            observed={
                "waypoints_completed": completed,
                "waypoints_total": total,
                "reached_all": bool(sim.metadata.get("reached_all", False)),
            },
            recommendation="Split the inspection into shorter sorties.",
        ),
        _check(
            check_id="turn_bank_feasibility",
            label="Turn / bank feasibility",
            margin=turn_margin,
            unit="rad/s",
            warning_margin=turn_warning,
            observed={"bank_max_deg": vehicle.get("bank_max_deg", None)},
            recommendation="Lower cruise speed or add more turn spacing.",
        ),
    ]

    checks_sorted = sorted(checks, key=lambda item: float(item["risk_points"]), reverse=True)
    hard_pass = bool(getattr(constraints, "hard_pass", False))
    robust_pass_rate = None if not robustness else robustness.get("hard_pass_rate")
    top_points = float(checks_sorted[0]["risk_points"]) if checks_sorted else 0.0
    if (not hard_pass) or top_points >= 70.0 or (
        robust_pass_rate is not None and float(robust_pass_rate) < 0.95
    ):
        mission_risk = "high"
    elif top_points >= 35.0 or (
        robust_pass_rate is not None and float(robust_pass_rate) < 1.0
    ):
        mission_risk = "medium"
    else:
        mission_risk = "low"

    return {
        "kind": "drone_inspection_constraint_audit",
        "mission_id": plan.metadata.get("mission_id", "aircraft_mission"),
        "status": "go" if hard_pass else "modify",
        "mission_risk": mission_risk,
        "top_limiting_constraint": checks_sorted[0] if checks_sorted else None,
        "top_three_risk_drivers": checks_sorted[:3],
        "checks": checks,
        "robustness": robustness or {},
        "summary": {
            "hard_constraints_pass": hard_pass,
            "inspection_points": max(0, len(plan.waypoints or []) - 1),
            "estimated_time_s": _scalar(sim, "t_end_s"),
            "energy_used_Wh": _scalar(sim, "energy_used_Wh"),
        },
    }


def format_inspection_constraint_audit(audit: Dict[str, Any]) -> str:
    """Render the drone inspection audit payload as Markdown."""
    top = audit.get("top_limiting_constraint") or {}
    lines = [
        "# Drone Inspection Constraint Audit",
        "",
        f"Mission: {audit.get('mission_id', 'aircraft_mission')}",
        f"Status: {str(audit.get('status', 'unknown')).upper()}",
        f"Mission risk: {str(audit.get('mission_risk', 'unknown')).upper()}",
        "",
        "## Top Limiting Constraint",
        "",
        (
            "- n/a"
            if not top
            else "- {label}: {status} with margin {margin} {unit}".format(
                label=top.get("label", "unknown"),
                status=str(top.get("status", "unknown")).upper(),
                margin=_fmt_value((top.get("margin") or {}).get("value")),
                unit=(top.get("margin") or {}).get("unit", ""),
            )
        ),
        "",
        "## Top Three Risk Drivers",
        "",
    ]
    for driver in audit.get("top_three_risk_drivers", []) or []:
        margin = driver.get("margin") or {}
        lines.append(
            "- {label}: {status}, margin {value} {unit}, risk points {points}".format(
                label=driver.get("label", "unknown"),
                status=str(driver.get("status", "unknown")).upper(),
                value=_fmt_value(margin.get("value")),
                unit=margin.get("unit", ""),
                points=_fmt_value(driver.get("risk_points")),
            )
        )

    lines.extend(["", "## Full Constraint Audit", ""])
    for check in audit.get("checks", []) or []:
        margin = check.get("margin") or {}
        observed = check.get("observed") or {}
        lines.extend(
            [
                f"### {check.get('label', 'Constraint')}",
                "",
                f"- Status: {str(check.get('status', 'unknown')).upper()}",
                f"- Margin: {_fmt_value(margin.get('value'))} {margin.get('unit', '')}",
                f"- Warning margin: "
                f"{_fmt_value((check.get('warning_margin') or {}).get('value'))} "
                f"{(check.get('warning_margin') or {}).get('unit', '')}",
                f"- Observed: `{strict_json_dumps(observed, sort_keys=True)}`",
                f"- Recommended action: {check.get('recommendation', 'Review mission plan.')}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def export_inspection_constraint_audit(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    out_dir: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write drone inspection audit JSON and Markdown artifacts."""
    audit = build_inspection_constraint_audit(
        plan,
        sim,
        constraints,
        cfg=cfg,
        robustness=robustness,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_strict_json(out_dir / "inspection_constraint_audit.json", audit)
    (out_dir / "inspection_constraint_audit.md").write_text(
        format_inspection_constraint_audit(audit),
        encoding="utf-8",
    )
    return audit


def _what_if_planner_config(cfg: Dict[str, Any], seed: int) -> PlannerConfig:
    planner_cfg = cfg.get("planner", {}) or {}
    mutation_cfg = planner_cfg.get("mutation", {}) or {}
    iterations = min(80, int(planner_cfg.get("iterations", 80)))
    return PlannerConfig(
        iterations=iterations,
        restarts=1,
        seed=seed,
        keep_history=False,
        scoring=ScoreConfig(
            penalty_weight=float(planner_cfg.get("penalty_weight", 1000.0)),
            margin_reward_weight=float(planner_cfg.get("margin_reward_weight", 0.0)),
        ),
        hard_infeasible_penalty=float(planner_cfg.get("hard_infeasible_penalty", 1e6)),
        mutation=MutationConfig(
            cont_sigma=float(mutation_cfg.get("cont_sigma", 0.10)),
            cont_sigma_is_frac=bool(mutation_cfg.get("cont_sigma_is_frac", True)),
            int_step=int(mutation_cfg.get("int_step", 1)),
            p_flip=float(mutation_cfg.get("p_flip", 0.05)),
            p_perm_swap=float(mutation_cfg.get("p_perm_swap", 0.50)),
            perm_swaps=int(mutation_cfg.get("perm_swaps", 2)),
        ),
    )


def _what_if_run_cfg(cfg: Dict[str, Any], seed: int) -> Dict[str, Any]:
    run_cfg = deepcopy(cfg)
    run_cfg.setdefault("robustness", {})
    run_cfg["robustness"]["cases"] = 0
    run_cfg.setdefault("planner", {})
    run_cfg["planner"]["seed"] = seed
    run_cfg["planner"]["iterations"] = min(80, int(run_cfg["planner"].get("iterations", 80)))
    run_cfg["planner"]["restarts"] = 1
    run_cfg.setdefault("output", {})
    run_cfg["output"]["save_history"] = False
    return run_cfg


def _solve_what_if_cfg(cfg: Dict[str, Any], seed: int) -> Any:
    from mission_framework.aircraft.mission import build_problem_from_config

    run_cfg = _what_if_run_cfg(cfg, seed)
    problem = build_problem_from_config(run_cfg)
    return Planner(_what_if_planner_config(run_cfg, seed)).solve(problem)


def _audit_check(audit: Dict[str, Any], check_id: str) -> Dict[str, Any]:
    for check in audit.get("checks", []) or []:
        if check.get("id") == check_id:
            return check
    return {}


def _check_margin_value(audit: Dict[str, Any], check_id: str) -> Optional[float]:
    check = _audit_check(audit, check_id)
    margin = check.get("margin") or {}
    value = margin.get("value")
    return None if value is None else float(value)


def _risk_rank(risk: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(risk).lower(), 3)


def _dedupe_risk_drivers(drivers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for driver in drivers:
        driver_id = str(driver.get("id", driver.get("label", "")))
        current = by_id.get(driver_id)
        if current is None or float(driver.get("risk_points", 0.0)) > float(
            current.get("risk_points", 0.0)
        ):
            by_id[driver_id] = driver
    return sorted(
        by_id.values(),
        key=lambda item: float(item.get("risk_points", 0.0)),
        reverse=True,
    )


def _variant_summary(
    *,
    variant_id: str,
    label: str,
    description: str,
    result: Any,
    cfg: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Dict[str, Any]:
    audit = build_inspection_constraint_audit(
        result.plan,
        result.sim_result,
        result.constraints,
        cfg=cfg,
        robustness=result.robustness,
    )
    time_s = _scalar(result.sim_result, "t_end_s")
    energy_wh = _scalar(result.sim_result, "energy_used_Wh")
    final_battery_wh = _scalar(result.sim_result, "final_battery_Wh")
    baseline_time = baseline.get("estimated_time_s")
    baseline_energy = baseline.get("energy_used_Wh")
    return {
        "id": variant_id,
        "label": label,
        "description": description,
        "feasible": bool(result.constraints.hard_pass),
        "mission_risk": audit["mission_risk"],
        "score": float(result.score),
        "estimated_time_s": time_s,
        "energy_used_Wh": energy_wh,
        "final_battery_Wh": final_battery_wh,
        "battery_reserve_margin_Wh": _check_margin_value(audit, "battery_reserve"),
        "wind_weather_margin_mps": _check_margin_value(audit, "wind_weather"),
        "geofence_clearance_margin_m": _check_margin_value(audit, "geofence_clearance"),
        "route_completion_margin": _check_margin_value(audit, "route_completion"),
        "turn_bank_margin_radps": _check_margin_value(audit, "turn_bank_feasibility"),
        "top_limiting_constraint": audit.get("top_limiting_constraint"),
        "top_three_risk_drivers": audit.get("top_three_risk_drivers", []),
        "delta_vs_baseline": {
            "estimated_time_s": (
                None if time_s is None or baseline_time is None else float(time_s - baseline_time)
            ),
            "energy_used_Wh": (
                None
                if energy_wh is None or baseline_energy is None
                else float(energy_wh - baseline_energy)
            ),
        },
    }


def _base_summary_from_audit(
    *,
    result_score: float,
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    audit: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": "baseline",
        "label": "Current BVLOS plan",
        "feasible": bool(getattr(constraints, "hard_pass", False)),
        "mission_risk": audit["mission_risk"],
        "score": float(result_score),
        "inspection_points": max(0, len(plan.waypoints or []) - 1),
        "estimated_time_s": _scalar(sim, "t_end_s"),
        "energy_used_Wh": _scalar(sim, "energy_used_Wh"),
        "final_battery_Wh": _scalar(sim, "final_battery_Wh"),
        "battery_reserve_margin_Wh": _check_margin_value(audit, "battery_reserve"),
        "wind_weather_margin_mps": _check_margin_value(audit, "wind_weather"),
        "geofence_clearance_margin_m": _check_margin_value(audit, "geofence_clearance"),
        "route_completion_margin": _check_margin_value(audit, "route_completion"),
        "turn_bank_margin_radps": _check_margin_value(audit, "turn_bank_feasibility"),
    }


def _fewer_waypoints_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    waypoints = list((out.get("mission", {}) or {}).get("waypoints", []) or [])
    keep = max(1, len(waypoints) - 2) if len(waypoints) >= 4 else max(1, len(waypoints) - 1)
    out["mission"]["waypoints"] = waypoints[:keep]
    return out


def _lower_speed_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    vehicle = out.get("vehicle", {}) or {}
    min_speed = float(vehicle.get("min_speed_mps", 12.0))
    cruise = float(vehicle.get("cruise_speed_mps", min_speed))
    lower_speed = max(min_speed, cruise * 0.8)
    vehicle["min_speed_mps"] = lower_speed
    vehicle["max_speed_mps"] = lower_speed
    vehicle["cruise_speed_mps"] = lower_speed
    out["vehicle"] = vehicle
    return out


def _alternate_launch_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    initial = out.get("initial_state", {}) or {}
    waypoints = list((out.get("mission", {}) or {}).get("waypoints", []) or [])
    if waypoints:
        first = waypoints[0]
        initial["x_m"] = float(initial.get("x_m", 0.0)) * 0.5 + float(first["x_m"]) * 0.5
        initial["y_m"] = float(initial.get("y_m", 0.0)) * 0.5 + float(first["y_m"]) * 0.5
    out["initial_state"] = initial
    return out


def _stronger_wind_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    wind = out.get("wind", {}) or {}
    for key in (
        "w_east_mps",
        "w_north_mps",
        "mean_east_mps",
        "mean_north_mps",
        "amp_east_mps",
        "amp_north_mps",
        "gust_amplitude_mps",
    ):
        if key in wind:
            wind[key] = float(wind[key]) * 1.5
    out["wind"] = wind
    return out


def _larger_reserve_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    vehicle = out.get("vehicle", {}) or {}
    capacity = float(vehicle.get("battery_capacity_Wh", 0.0))
    current_reserve = float(vehicle.get("battery_reserve_Wh", 0.0))
    larger_reserve = max(current_reserve + 100.0, current_reserve * 1.15)
    if capacity > 0.0:
        larger_reserve = min(capacity * 0.95, larger_reserve)
    vehicle["battery_reserve_Wh"] = larger_reserve
    out["vehicle"] = vehicle
    out.setdefault("constraints", {})
    out["constraints"]["enforce_battery_reserve"] = True
    return out


def _relaunch_sortie_cfgs(cfg: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    waypoints = list((cfg.get("mission", {}) or {}).get("waypoints", []) or [])
    if len(waypoints) < 2:
        return None

    split = int(np.ceil(len(waypoints) / 2.0))
    first_leg = deepcopy(cfg)
    second_leg = deepcopy(cfg)
    first_leg["mission"]["waypoints"] = waypoints[:split]
    second_leg["mission"]["waypoints"] = waypoints[split:]
    if not second_leg["mission"]["waypoints"]:
        return None

    swap_point = waypoints[split - 1]
    second_initial = second_leg.get("initial_state", {}) or {}
    second_initial["x_m"] = float(swap_point["x_m"])
    second_initial["y_m"] = float(swap_point["y_m"])
    second_initial["z_m"] = float(swap_point.get("z_m", second_initial.get("z_m", 0.0)))
    vehicle = second_leg.get("vehicle", {}) or {}
    capacity = float(vehicle.get("battery_capacity_Wh", second_initial.get("battery_Wh", 0.0)))
    original_initial = float((cfg.get("initial_state", {}) or {}).get("battery_Wh", capacity))
    second_initial["battery_Wh"] = min(capacity, original_initial)
    second_leg["initial_state"] = second_initial
    return [first_leg, second_leg]


def _relaunch_summary(
    *,
    cfg: Dict[str, Any],
    baseline: Dict[str, Any],
    seed: int,
) -> Optional[Dict[str, Any]]:
    sortie_cfgs = _relaunch_sortie_cfgs(cfg)
    if sortie_cfgs is None:
        return None

    sortie_summaries = []
    for index, sortie_cfg in enumerate(sortie_cfgs):
        result = _solve_what_if_cfg(sortie_cfg, seed + index)
        sortie_summaries.append(
            _variant_summary(
                variant_id=f"relaunch_battery_swap_sortie_{index + 1}",
                label=f"Relaunch / battery swap sortie {index + 1}",
                description="One sortie in a split-route battery swap option.",
                result=result,
                cfg=sortie_cfg,
                baseline=baseline,
            )
        )

    total_time = sum(float(s.get("estimated_time_s") or 0.0) for s in sortie_summaries)
    total_energy = sum(float(s.get("energy_used_Wh") or 0.0) for s in sortie_summaries)
    feasible = all(bool(s["feasible"]) for s in sortie_summaries)
    worst_risk = max((str(s["mission_risk"]) for s in sortie_summaries), key=_risk_rank)
    drivers = _dedupe_risk_drivers(
        driver
        for summary in sortie_summaries
        for driver in summary.get("top_three_risk_drivers", [])[:3]
    )[:3]
    baseline_time = baseline.get("estimated_time_s")
    baseline_energy = baseline.get("energy_used_Wh")
    return {
        "id": "relaunch_battery_swap",
        "label": "Relaunch / battery swap",
        "description": "Split the route into two sorties with a fresh battery for the second leg.",
        "feasible": feasible,
        "mission_risk": worst_risk,
        "score": sum(float(s.get("score") or 0.0) for s in sortie_summaries),
        "estimated_time_s": total_time,
        "energy_used_Wh": total_energy,
        "final_battery_Wh": min(float(s.get("final_battery_Wh") or 0.0) for s in sortie_summaries),
        "battery_reserve_margin_Wh": min(
            float(s.get("battery_reserve_margin_Wh") or 0.0) for s in sortie_summaries
        ),
        "wind_weather_margin_mps": min(
            float(s.get("wind_weather_margin_mps") or 0.0) for s in sortie_summaries
        ),
        "geofence_clearance_margin_m": min(
            float(s.get("geofence_clearance_margin_m") or 0.0) for s in sortie_summaries
        ),
        "route_completion_margin": min(
            float(s.get("route_completion_margin") or 0.0) for s in sortie_summaries
        ),
        "turn_bank_margin_radps": min(
            float(s.get("turn_bank_margin_radps") or 0.0) for s in sortie_summaries
        ),
        "top_limiting_constraint": drivers[0] if drivers else None,
        "top_three_risk_drivers": drivers,
        "sorties": sortie_summaries,
        "delta_vs_baseline": {
            "estimated_time_s": (
                None if baseline_time is None else float(total_time - float(baseline_time))
            ),
            "energy_used_Wh": (
                None if baseline_energy is None else float(total_energy - float(baseline_energy))
            ),
        },
    }


def build_what_if_plan(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    *,
    cfg: Dict[str, Any],
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare practical BVLOS inspection what-if planning options."""
    base_audit = build_inspection_constraint_audit(
        plan,
        sim,
        constraints,
        cfg=cfg,
        robustness=robustness,
    )
    baseline = _base_summary_from_audit(
        result_score=float(getattr(score_report, "total_score", 0.0)),
        plan=plan,
        sim=sim,
        constraints=constraints,
        audit=base_audit,
    )
    seed = int((cfg.get("planner", {}) or {}).get("seed", 0)) + 1000
    variant_specs = [
        (
            "fewer_waypoints",
            "Fewer waypoints",
            "Drop the final inspection points to compare a shorter sortie.",
            _fewer_waypoints_cfg,
        ),
        (
            "lower_speed",
            "Lower speed",
            "Force a lower cruise speed to compare endurance and turn margin.",
            _lower_speed_cfg,
        ),
        (
            "alternate_launch_point",
            "Alternate launch point",
            "Move launch closer to the first tower / inspection corridor.",
            _alternate_launch_cfg,
        ),
        (
            "stronger_wind",
            "Stronger wind case",
            "Increase modeled wind components by 50 percent.",
            _stronger_wind_cfg,
        ),
        (
            "larger_battery_reserve",
            "Larger battery reserve requirement",
            "Increase the required final battery reserve.",
            _larger_reserve_cfg,
        ),
    ]

    variants = []
    for index, (variant_id, label, description, factory) in enumerate(variant_specs):
        variant_cfg = factory(cfg)
        result = _solve_what_if_cfg(variant_cfg, seed + index)
        variants.append(
            _variant_summary(
                variant_id=variant_id,
                label=label,
                description=description,
                result=result,
                cfg=variant_cfg,
                baseline=baseline,
            )
        )

    relaunch = _relaunch_summary(cfg=cfg, baseline=baseline, seed=seed + len(variant_specs))
    if relaunch is not None:
        variants.append(relaunch)

    return {
        "kind": "drone_inspection_what_if_plan",
        "mission_id": plan.metadata.get("mission_id", "aircraft_mission"),
        "baseline": baseline,
        "variants": variants,
    }


def format_what_if_plan(payload: Dict[str, Any]) -> str:
    """Render what-if planning comparisons as Markdown."""
    lines = [
        "# BVLOS What-If Planning",
        "",
        f"Mission: {payload.get('mission_id', 'aircraft_mission')}",
        "",
        "## Baseline",
        "",
        "| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    base = payload.get("baseline", {}) or {}
    lines.append(
        "| {risk} | {feasible} | {time} | {energy} | {battery} | {wind} |".format(
            risk=str(base.get("mission_risk", "unknown")).upper(),
            feasible="yes" if base.get("feasible") else "no",
            time=_fmt_value(base.get("estimated_time_s")),
            energy=_fmt_value(base.get("energy_used_Wh")),
            battery=_fmt_value(base.get("battery_reserve_margin_Wh")),
            wind=_fmt_value(base.get("wind_weather_margin_mps")),
        )
    )

    lines.extend(
        [
            "",
            "## Scenario Comparisons",
            "",
            "| Scenario | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | "
            "Battery Margin | Top Limiter |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for variant in payload.get("variants", []) or []:
        top = variant.get("top_limiting_constraint") or {}
        delta = variant.get("delta_vs_baseline") or {}
        lines.append(
            "| {label} | {risk} | {feasible} | {time} | {delta_time} | {energy} | "
            "{battery} | {limiter} |".format(
                label=variant.get("label", "Scenario"),
                risk=str(variant.get("mission_risk", "unknown")).upper(),
                feasible="yes" if variant.get("feasible") else "no",
                time=_fmt_value(variant.get("estimated_time_s")),
                delta_time=_fmt_value(delta.get("estimated_time_s")),
                energy=_fmt_value(variant.get("energy_used_Wh")),
                battery=_fmt_value(variant.get("battery_reserve_margin_Wh")),
                limiter=top.get("label", "n/a"),
            )
        )

    lines.extend(["", "## Notes", ""])
    for variant in payload.get("variants", []) or []:
        lines.append(f"- {variant.get('label', 'Scenario')}: {variant.get('description', '')}")
    return "\n".join(lines).rstrip() + "\n"


def export_what_if_plan(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    out_dir: Path,
    *,
    cfg: Dict[str, Any],
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write BVLOS what-if planning JSON and Markdown artifacts."""
    payload = build_what_if_plan(
        plan,
        sim,
        constraints,
        score_report,
        cfg=cfg,
        robustness=robustness,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_strict_json(out_dir / "what_if_plan.json", payload)
    (out_dir / "what_if_plan.md").write_text(format_what_if_plan(payload), encoding="utf-8")
    return payload


def export_operator_memo(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    out_path: Path,
    robustness: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Write a lightweight go/no-go memo for BVLOS inspection planning review.

    This is additive reporting only; core JSON contracts remain unchanged.
    """
    hard_pass = bool(getattr(constraints, "hard_pass", False))
    status = "GO" if hard_pass else "MODIFY / DO NOT FLY"
    waypoints = plan.waypoints or []
    inspection_points = max(0, len(waypoints) - 1)
    hard = sorted(list(_hard_constraints(constraints)), key=lambda result: result.min_margin)

    lines = [
        "# BVLOS Inspection Operator Memo",
        "",
        f"Status: {status}",
        "",
        "ORBITAL is preflight decision support and audit evidence. It is not a LAANC "
        "provider, autopilot, or regulatory approval system.",
        "",
        "## Mission Summary",
        "",
        f"- Mission: {plan.metadata.get('mission_id', 'aircraft_mission')}",
        f"- Inspection points: {inspection_points}",
        f"- Planned cruise speed: {_fmt_value(plan.metadata.get('cruise_speed_mps'), 'm/s')}",
        f"- Estimated flight time: {_fmt_value(_scalar(sim, 't_end_s'), 's')}",
        f"- Estimated energy used: {_fmt_value(_scalar(sim, 'energy_used_Wh'), 'Wh')}",
        f"- Final battery: {_fmt_value(_scalar(sim, 'final_battery_Wh'), 'Wh')}",
        f"- Objective score: {_fmt_value(getattr(score_report, 'total_score', None))}",
        "",
        "## Top Constraints",
        "",
    ]

    if hard:
        for result in hard[:5]:
            state = "PASS" if bool(result.is_satisfied) else "REVIEW"
            lines.append(
                f"- {state}: {_constraint_label(str(result.name))} "
                f"(margin {_fmt_value(float(result.min_margin))})"
            )
    else:
        lines.append("- No hard constraints were reported.")

    if robustness:
        lines.extend(
            [
                "",
                "## Robustness",
                "",
                f"- Cases: {robustness.get('cases', 'n/a')}",
                f"- Hard pass rate: {_fmt_value(robustness.get('hard_pass_rate'))}",
                "- Worst hard margin across cases: "
                f"{_fmt_value(robustness.get('worst_hard_margin_min'))}",
            ]
        )

    lines.extend(["", "## Recommended Next Actions", ""])
    lines.extend(f"- {action}" for action in _recommended_actions(constraints))

    memo = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(memo, encoding="utf-8")
    return memo


def print_flight_plan(plan: Plan, max_rows: int = 50) -> str:
    """
    Return a pretty text table for console printing.
    """
    rows = flight_plan_table(plan)
    rows = rows[:max_rows]

    # Pick common columns first
    preferred = ["seq", "id", "eta_s", "x_m", "y_m", "z_m", "lat_deg", "lon_deg", "alt_m"]
    columns = [c for c in preferred if any(c in r for r in rows)]
    # Add any other columns
    for r in rows:
        for k in r.keys():
            if k not in columns:
                columns.append(k)

    # Compute widths
    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v)

    widths = {c: max(len(c), *(len(_fmt(r.get(c, ""))) for r in rows)) for c in columns}

    lines = []
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    lines.append(header)
    lines.append(sep)

    for r in rows:
        lines.append(" | ".join(_fmt(r.get(c, "")).ljust(widths[c]) for c in columns))

    if len(flight_plan_table(plan)) > max_rows:
        lines.append(f"... ({len(flight_plan_table(plan)) - max_rows} more rows)")

    return "\n".join(lines)
