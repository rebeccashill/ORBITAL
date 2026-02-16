# mission_framework/simulation/feasibility.py
"""
Feasibility utilities (constraint checking helpers) for simulations.

This module sits between:
- simulation outputs (SimulationResult / sim object)
and
- the constraint system (core/constraints.py)

It provides:
- quick feasibility checks (hard-only or hard+soft)
- compact summaries for logging/debugging
- simple score shaping helpers (penalize infeasible runs)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from mission_framework.core.constraints import (
    Constraint,
    ConstraintReport,
    Severity,
    evaluate_constraints,
)


# ============================================================
# Summary structures
# ============================================================

@dataclass(frozen=True)
class FeasibilitySummary:
    """Compact feasibility view that’s easy to print/log."""
    hard_pass: bool
    soft_pass: bool
    min_hard_margin: float
    min_soft_margin: float
    violated_hard: List[str]
    violated_soft: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "hard_pass": bool(self.hard_pass),
            "soft_pass": bool(self.soft_pass),
            "min_hard_margin": float(self.min_hard_margin),
            "min_soft_margin": float(self.min_soft_margin),
            "violated_hard": list(self.violated_hard),
            "violated_soft": list(self.violated_soft),
        }


# ============================================================
# Core helpers
# ============================================================

def is_feasible(
    sim: Any,
    constraints: Sequence[Constraint],
    *,
    require_soft: bool = False,
) -> Tuple[bool, ConstraintReport]:
    """
    Evaluate constraints and return (feasible?, report).

    Default: feasible means all HARD constraints pass.
    If require_soft=True: both HARD and SOFT must pass.
    """
    report = evaluate_constraints(sim, constraints)
    ok = bool(report.hard_pass and (report.soft_pass if require_soft else True))
    return ok, report


def is_hard_feasible(report: ConstraintReport) -> bool:
    """True if all HARD constraints pass."""
    return bool(report.hard_pass)


def feasibility_summary(report: ConstraintReport) -> FeasibilitySummary:
    """Build a compact feasibility summary from a full ConstraintReport."""
    worst_hard = report.worst(Severity.HARD)
    worst_soft = report.worst(Severity.SOFT)

    violated_hard = [
        r.name for r in report.results
        if r.severity == Severity.HARD and not r.is_satisfied
    ]
    violated_soft = [
        r.name for r in report.results
        if r.severity == Severity.SOFT and not r.is_satisfied
    ]

    return FeasibilitySummary(
        hard_pass=bool(report.hard_pass),
        soft_pass=bool(report.soft_pass),
        min_hard_margin=float(worst_hard.min_margin) if worst_hard is not None else float("inf"),
        min_soft_margin=float(worst_soft.min_margin) if worst_soft is not None else float("inf"),
        violated_hard=violated_hard,
        violated_soft=violated_soft,
    )


def hard_feasibility_margin(report: ConstraintReport) -> float:
    """Minimum margin over HARD constraints (inf if none)."""
    w = report.worst(Severity.HARD)
    return float(w.min_margin) if w is not None else float("inf")


def soft_feasibility_margin(report: ConstraintReport) -> float:
    """Minimum margin over SOFT constraints (inf if none)."""
    w = report.worst(Severity.SOFT)
    return float(w.min_margin) if w is not None else float("inf")


# ============================================================
# Scoring helpers
# ============================================================

def shaped_score(
    objective_cost: float,
    report: ConstraintReport,
    *,
    penalty_weight: float = 1000.0,
    hard_infeasible_penalty: float = 1e6,
    include_hard_penalty: bool = True,
    include_soft_penalty: bool = True,
) -> float:
    """
    Convenience scoring pattern for planners/optimizers:

        shaped = objective_cost
                 + penalty_weight * (constraint penalties)
                 + hard_infeasible_penalty if any hard constraint violated

    Use this if your search benefits from "gradient-ish" penalty guidance even when infeasible.
    """
    penalty = report.total_penalty(include_hard=include_hard_penalty, include_soft=include_soft_penalty)
    shaped = float(objective_cost + penalty_weight * penalty)
    if not report.hard_pass:
        shaped += float(hard_infeasible_penalty)
    return float(shaped)


def rank_by_feasibility_then_score(
    candidates: Sequence[Tuple[float, ConstraintReport]],
) -> List[int]:
    """
    Given candidates as (score, report), return indices sorted by:
      1) hard feasible first
      2) larger min hard margin first (more robust)
      3) lower score first

    Useful for selection steps in CEM/evolutionary/random search.
    """
    keyed: List[Tuple[int, int, float, float]] = []
    for i, (score, rep) in enumerate(candidates):
        feas = 1 if rep.hard_pass else 0
        margin = hard_feasibility_margin(rep)
        keyed.append((i, feas, float(margin), float(score)))

    keyed_sorted = sorted(keyed, key=lambda t: (-t[1], -t[2], t[3]))
    return [t[0] for t in keyed_sorted]

def format_feasibility_report(report: ConstraintReport, max_lines: int = 50) -> str:
    """
    Human-readable report string for CLI output.

    Sorted worst-first (lowest min_margin). Shows pass/fail, severity, margins, penalty.
    """
    lines: List[str] = []
    lines.append(
        f"HARD pass: {report.hard_pass} | SOFT pass: {report.soft_pass} | total_penalty: {report.total_penalty():.6g}"
    )

    # sort constraints by worst margin
    sorted_results = sorted(report.results, key=lambda r: r.min_margin)

    for r in sorted_results[:max_lines]:
        status = "PASS" if r.is_satisfied else "FAIL"
        sev = r.severity.value.upper() if hasattr(r.severity, "value") else str(r.severity).upper()
        lines.append(
            f"[{status}] {sev:4s}  {r.name:30s}  "
            f"min_margin={r.min_margin:+.6g}  max_violation={r.max_violation:.6g}  penalty={r.penalty():.6g}"
        )

    if len(sorted_results) > max_lines:
        lines.append(f"... ({len(sorted_results) - max_lines} more constraints not shown)")

    return "\n".join(lines)
