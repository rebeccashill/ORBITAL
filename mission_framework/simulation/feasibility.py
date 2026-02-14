# mission_framework/core/feasibility.py
"""
Feasibility utilities (constraint-checking helpers).

This module sits *on top of* `constraints.py` and provides convenience functions for:
- Quick feasibility checks (hard constraints only)
- Compact feasibility summaries (worst margin, violated names)
- Simple “score shaping” helpers (e.g., add big penalty if hard-infeasible)

It stays domain-agnostic: it only depends on the simulation output/context object
and the constraint system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from mission_framework.core.constraints import (
    Constraint,
    ConstraintReport,
    Severity,
    evaluate_constraints,
)


@dataclass(frozen=True)
class FeasibilitySummary:
    """A compact view of feasibility that’s easy to log/print."""
    hard_pass: bool
    soft_pass: bool
    min_hard_margin: float
    min_soft_margin: float
    violated_hard: List[str]
    violated_soft: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hard_pass": bool(self.hard_pass),
            "soft_pass": bool(self.soft_pass),
            "min_hard_margin": float(self.min_hard_margin),
            "min_soft_margin": float(self.min_soft_margin),
            "violated_hard": list(self.violated_hard),
            "violated_soft": list(self.violated_soft),
        }


def feasibility_summary(report: ConstraintReport) -> FeasibilitySummary:
    """Build a compact feasibility summary from a full ConstraintReport."""
    worst_hard = report.worst(Severity.HARD)
    worst_soft = report.worst(Severity.SOFT)

    violated_hard = [r.name for r in report.results if r.severity == Severity.HARD and not r.is_satisfied]
    violated_soft = [r.name for r in report.results if r.severity == Severity.SOFT and not r.is_satisfied]

    return FeasibilitySummary(
        hard_pass=bool(report.hard_pass),
        soft_pass=bool(report.soft_pass),
        min_hard_margin=float(worst_hard.min_margin) if worst_hard is not None else float("inf"),
        min_soft_margin=float(worst_soft.min_margin) if worst_soft is not None else float("inf"),
        violated_hard=violated_hard,
        violated_soft=violated_soft,
    )


def is_hard_feasible(report: ConstraintReport) -> bool:
    """True if all HARD constraints pass."""
    return bool(report.hard_pass)


def is_feasible(
    sim: Any,
    constraints: Sequence[Constraint],
    *,
    require_soft: bool = False,
) -> Tuple[bool, ConstraintReport]:
    """
    Evaluate constraints and return (feasible?, report).

    By default, feasibility means HARD constraints pass.
    If require_soft=True, then both HARD and SOFT must pass.
    """
    report = evaluate_constraints(sim, constraints)
    ok = report.hard_pass and (report.soft_pass if require_soft else True)
    return bool(ok), report


def hard_feasibility_margin(report: ConstraintReport) -> float:
    """
    Return the minimum margin over HARD constraints (inf if none).
    Useful for sorting candidates by “how close to feasible”.
    """
    w = report.worst(Severity.HARD)
    return float(w.min_margin) if w is not None else float("inf")


def soft_feasibility_margin(report: ConstraintReport) -> float:
    """Return the minimum margin over SOFT constraints (inf if none)."""
    w = report.worst(Severity.SOFT)
    return float(w.min_margin) if w is not None else float("inf")


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
    Common hackathon scoring pattern:
        score = objective_cost + penalty_weight * total_penalty + (hard_infeasible ? big_M : 0)

    Notes:
    - `ConstraintResult.penalty()` is a smooth penalty (sum of squared violations) with per-constraint weights.
    - We often still include hard-constraint penalties to guide search back to feasibility.
    """
    penalty = report.total_penalty(include_hard=include_hard_penalty, include_soft=include_soft_penalty)
    score = float(objective_cost + penalty_weight * penalty)
    if not report.hard_pass:
        score += float(hard_infeasible_penalty)
    return float(score)


def rank_by_feasibility_then_score(
    candidates: Sequence[Tuple[float, ConstraintReport]],
) -> List[int]:
    """
    Given a list of (score, report), return indices sorted by:
    1) hard feasible first
    2) higher min hard margin (closer to / more robustly feasible) first
    3) lower score first

    This is handy for selection in evolutionary / CEM loops.
    """
    keys = []
    for i, (score, rep) in enumerate(candidates):
        feas = 1 if rep.hard_pass else 0
        margin = hard_feasibility_margin(rep)
        keys.append((i, feas, margin, float(score)))

    # Sort: feasible desc, margin desc, score asc
    keys_sorted = sorted(keys, key=lambda t: (-t[1], -t[2], t[3]))
    return [t[0] for t in keys_sorted]


def finite_min(x: Sequence[float]) -> float:
    """Utility: min ignoring NaNs/infs; returns inf if no finite values."""
    arr = np.array(list(x), dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return float("inf")
    return float(np.min(finite))
