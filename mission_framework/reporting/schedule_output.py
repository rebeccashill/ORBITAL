# mission_framework/reporting/schedule_output.py
"""
Schedule output utilities (Spacecraft Module B).

Exports:
- A time-ordered 7-day schedule of events (observations/downlinks/slew/idle)
- Optional supporting evidence fields (visibility/contact metadata)
- JSON + CSV-friendly formats
- Pretty console table

Expected inputs:
- Plan.kind == "spacecraft"
- Plan.schedule: Schedule containing Event objects
- Optionally SimResult.schedule (executed schedule) + SimResult.scalars/resources/metadata
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from mission_framework.core.types import Event, EventType, Plan, Schedule, SimResult


def _to_iso_utc(epoch_utc: Optional[str], t_s: float) -> Optional[str]:
    """
    Convert seconds-from-epoch to ISO UTC if epoch_utc provided.
    epoch_utc should be like "2026-01-01T00:00:00Z".
    """
    if not epoch_utc:
        return None
    # Parse ISO Z
    s = epoch_utc.replace("Z", "+00:00")
    epoch = datetime.fromisoformat(s).astimezone(timezone.utc)
    dt = epoch.timestamp() + float(t_s)
    return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def schedule_rows(schedule: Schedule, epoch_utc: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convert a Schedule into a list of rows (dicts).

    Includes both seconds-from-epoch and ISO UTC (if epoch_utc provided).
    """
    rows: List[Dict[str, Any]] = []
    for i, e in enumerate(schedule.sorted().events):
        row: Dict[str, Any] = {
            "seq": i,
            "etype": str(e.etype.value if hasattr(e.etype, "value") else e.etype),
            "label": e.label,
            "target_id": e.target_id,
            "t_start_s": float(e.t_start),
            "t_end_s": float(e.t_end),
            "duration_s": float(e.duration),
        }
        if e.location is not None:
            row["lat_deg"] = float(e.location[0])
            row["lon_deg"] = float(e.location[1])

        t0 = _to_iso_utc(epoch_utc, e.t_start)
        t1 = _to_iso_utc(epoch_utc, e.t_end)
        if t0 is not None:
            row["t_start_utc"] = t0
        if t1 is not None:
            row["t_end_utc"] = t1

        # include any extra evidence fields
        if e.data:
            for k, v in e.data.items():
                # avoid collisions
                key = k if k not in row else f"data_{k}"
                row[key] = v

        rows.append(row)
    return rows


def export_schedule_json(
    plan: Plan,
    sim: Optional[SimResult] = None,
    out_path: Optional[Path] = None,
    epoch_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create (and optionally write) a JSON export containing:
    - planned schedule table
    - optional simulated/executed schedule
    - optional resources + scalars
    """
    if plan.kind != "spacecraft":
        raise ValueError(f"export_schedule_json expects plan.kind='spacecraft', got '{plan.kind}'")

    if plan.schedule is None:
        raise ValueError("Plan.schedule is required for spacecraft schedule export.")

    payload: Dict[str, Any] = {
        "kind": plan.kind,
        "epoch_utc": epoch_utc,
        "schedule": schedule_rows(plan.schedule, epoch_utc=epoch_utc),
        "plan_metadata": dict(plan.metadata),
    }

    if sim is not None:
        # If sim has an executed schedule, export it too
        sched = sim.schedule if sim.schedule is not None else None
        if sched is not None:
            payload["executed_schedule"] = schedule_rows(sched, epoch_utc=epoch_utc)

        payload["resources"] = {k: np.asarray(v, dtype=float).tolist() for k, v in sim.resources.items()}
        payload["scalars"] = dict(sim.scalars)
        payload["sim_metadata"] = dict(sim.metadata)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    return payload


def export_schedule_csv(plan: Plan, out_path: Path, epoch_utc: Optional[str] = None) -> None:
    """Export planned schedule as CSV."""
    if plan.schedule is None:
        raise ValueError("Plan.schedule is required for schedule CSV export.")
    rows = schedule_rows(plan.schedule, epoch_utc=epoch_utc)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # union of keys for header
    keys: List[str] = []
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

from pathlib import Path
from typing import Any, Dict, List, Optional

from mission_framework.core.types import Plan, Event

def schedule_table(plan: Plan) -> List[Dict[str, Any]]:
    if plan.kind != "spacecraft" or plan.schedule is None:
        raise ValueError(f"schedule_table expects plan.kind='spacecraft' with schedule, got '{plan.kind}'")

    rows: List[Dict[str, Any]] = []
    for i, e in enumerate(plan.schedule.events):
        loc = e.location
        data = e.data or {}
        rows.append({
            "seq": i,
            "etype": str(e.etype),
            "label": e.label,
            "target_id": e.target_id or "",
            "t_start_s": float(e.t_start),
            "t_end_s": float(e.t_end),
            "duration_s": float(e.t_end - e.t_start),
            "lat_deg": loc[0] if loc is not None else "",
            "lon_deg": loc[1] if loc is not None else "",
            "station_id": "",
            "data_duration_s": data.get("duration_s", ""),
            "value": data.get("value", ""),
        })
    return rows


def print_schedule(plan: Plan, max_rows: int = 80, epoch_utc: Optional[str] = None) -> str:
    """Pretty console table for the schedule."""
    if plan.schedule is None:
        return "(no schedule)"

    rows = schedule_rows(plan.schedule, epoch_utc=epoch_utc)
    shown = rows[:max_rows]

    preferred = [
        "seq",
        "etype",
        "label",
        "target_id",
        "t_start_utc" if epoch_utc else "t_start_s",
        "t_end_utc" if epoch_utc else "t_end_s",
        "duration_s",
    ]
    columns = [c for c in preferred if any(c in r for r in shown)]
    for r in shown:
        for k in r.keys():
            if k not in columns:
                columns.append(k)

    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    widths = {c: max(len(c), *(len(_fmt(r.get(c, ""))) for r in shown)) for c in columns}

    lines = []
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    lines.append(header)
    lines.append(sep)

    for r in shown:
        lines.append(" | ".join(_fmt(r.get(c, "")).ljust(widths[c]) for c in columns))

    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)
