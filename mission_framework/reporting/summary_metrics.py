# mission_framework/reporting/summary_metrics.py
"""
Summary metrics utilities.

Purpose:
- Provide a simple, consistent set of mission performance metrics for BOTH domains.
- Convert SimResult contents into a JSON-friendly metrics dict.

This is intentionally generic:
- It reads from SimResult.scalars (preferred) and SimResult.resources (optional).
- Domain modules should populate SimResult.scalars with the keys they care about.

Recommended scalar keys (not all required):
Aircraft:
- t_end_s
- distance_m
- energy_used_Wh
- final_battery_Wh
- avg_groundspeed_mps

Spacecraft:
- mission_value
- value_downlinked
- observations_completed
- downlinks_completed
- data_generated_Gb
- data_downlinked_Gb
- final_battery_Wh

Robustness (if provided elsewhere):
- hard_pass_rate
- p50_score / p90_score
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from mission_framework.core.types import SimResult


DEFAULT_KEYS = [
    # Common
    "t_end_s",
    "energy_used_Wh",
    "final_battery_Wh",
    # Aircraft-ish
    "distance_m",
    "avg_groundspeed_mps",
    # Spacecraft-ish
    "mission_value",
    "value_downlinked",
    "observations_completed",
    "downlinks_completed",
    "data_generated_Gb",
    "data_downlinked_Gb",
]


def compute_summary_metrics(sim: SimResult, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract a compact metrics dict from SimResult.

    - Pulls known keys from sim.scalars if present.
    - Adds derived metrics when possible (e.g., t_end_s from sim.t).
    - Optionally merges in `extra` (e.g., robustness summary).
    """
    metrics: Dict[str, Any] = {}

    # Prefer scalar keys explicitly set by domain sim
    for k in DEFAULT_KEYS:
        if k in sim.scalars:
            metrics[k] = float(sim.scalars[k])

    # Derived: t_end_s if not provided
    if "t_end_s" not in metrics and sim.t is not None and len(sim.t) > 0:
        metrics["t_end_s"] = float(np.asarray(sim.t, dtype=float)[-1])

    # Derived: final battery from a resource trace, if present
    if "final_battery_Wh" not in metrics and "battery_Wh" in sim.resources:
        metrics["final_battery_Wh"] = float(np.asarray(sim.resources["battery_Wh"], dtype=float)[-1])

    # Derived: energy used if have battery trace and capacity info in metadata
    # (Optional heuristic; domains should set energy_used_Wh explicitly when possible.)
    if "energy_used_Wh" not in metrics and "battery_Wh" in sim.resources:
        b = np.asarray(sim.resources["battery_Wh"], dtype=float)
        # naive: energy used ~ max(b) - min(b) isn't correct if recharge occurs; leave it out by default
        # but if metadata indicates no charging, approximate:
        if sim.metadata.get("battery_no_recharge", False):
            metrics["energy_used_Wh"] = float(b[0] - b[-1])

    # Include any additional metrics (e.g., robustness summary)
    if extra:
        for k, v in extra.items():
            metrics[k] = v

    return metrics


def export_summary_metrics_json(sim: SimResult, out_path: Optional[Path] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = compute_summary_metrics(sim, extra=extra)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
