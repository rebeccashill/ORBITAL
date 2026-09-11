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
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from mission_framework.core.json_utils import write_strict_json
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
