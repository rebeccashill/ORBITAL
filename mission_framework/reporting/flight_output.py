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

Hackathon tip:
- Keep exports simple and readable.
- Judges love "here's the flight plan table" plus a constraint report and metrics.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

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
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

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
