# mission_framework/reporting/constraint_report.py
"""
Constraint report exporting utilities.

This module turns a ConstraintReport into:
- JSON-friendly dicts
- CSV tables
- Pretty console text

Works for BOTH aircraft and spacecraft because ConstraintReport is domain-agnostic.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from mission_framework.core.constraints import ConstraintReport, ConstraintResult, Severity


def constraint_rows(report: ConstraintReport) -> List[Dict[str, Any]]:
    """One row per constraint (summary, not per-sample margin)."""
    rows: List[Dict[str, Any]] = []
    for r in report.results:
        rows.append({
            "name": r.name,
            "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
            "status": "PASS" if r.is_satisfied else "FAIL",
            "min_margin": float(r.min_margin),
            "max_violation": float(r.max_violation),
            "penalty": float(r.penalty()),
            "reduce_mode": r.reduce_mode.value if hasattr(r.reduce_mode, "value") else str(r.reduce_mode),
            "weight": float(r.weight),
        })
    # Sort worst first (lowest min_margin)
    rows.sort(key=lambda x: x["min_margin"])
    return rows


def export_constraint_report_json(report: ConstraintReport, out_path: Optional[Path] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "summary": report.summary(),
        "constraints": constraint_rows(report),
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def export_constraint_report_csv(report: ConstraintReport, out_path: Path) -> None:
    rows = constraint_rows(report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys()) if rows else ["name", "severity", "status", "min_margin", "max_violation", "penalty"]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def print_constraint_report(report: ConstraintReport, max_rows: int = 60) -> str:
    rows = constraint_rows(report)[:max_rows]

    preferred = ["status", "severity", "name", "min_margin", "max_violation", "penalty"]
    cols = [c for c in preferred if any(c in r for r in rows)]
    for r in rows:
        for k in r.keys():
            if k not in cols:
                cols.append(k)

    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:+.6g}"
        return str(v)

    widths = {c: max(len(c), *(len(_fmt(r.get(c, ""))) for r in rows)) for c in cols}

    lines: List[str] = []
    lines.append(f"HARD pass: {report.hard_pass} | SOFT pass: {report.soft_pass} | total_penalty: {report.total_penalty():.6g}")

    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    lines.append(header)
    lines.append(sep)

    for r in rows:
        lines.append(" | ".join(_fmt(r.get(c, "")).ljust(widths[c]) for c in cols))

    if len(constraint_rows(report)) > max_rows:
        lines.append(f"... ({len(constraint_rows(report)) - max_rows} more rows)")

    return "\n".join(lines)


def worst_constraint(report: ConstraintReport, severity: Optional[Severity] = None) -> Optional[ConstraintResult]:
    """Return the worst (lowest min margin) constraint optionally filtered by severity."""
    return report.worst(severity=severity)
