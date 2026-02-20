# mission_framework/core/solutions.py
"""
Solution containers (domain-agnostic).

This file defines lightweight data structures for returning results from the planner.

Design goals:
- Domain-agnostic: works for aircraft missions AND spacecraft schedules.
- Easy to inspect/print: good for hackathon demos and debugging.
- Minimal coupling: does NOT assume any specific simulation state type.

Typical usage (as in your `main.py`):
    result = planner.solve(problem)

    result.sim_result["t_end_s"]
    result.constraints.hard_pass
    result.objective.total_cost()
    result.score
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ConstraintEvaluation:
    """
    Summary of constraint checking for one simulation run.

    `margins` stores the numeric margin per constraint:
      margin >= 0  -> satisfied
      margin <  0  -> violated (magnitude indicates severity)

    `hard_pass` is True only if all HARD constraints are satisfied.
    `soft_pass` is True only if all SOFT constraints are satisfied.
    """

    margins: Dict[str, float] = field(default_factory=dict)
    hard_pass: bool = True
    soft_pass: bool = True

    hard_violations: Tuple[str, ...] = ()
    soft_violations: Tuple[str, ...] = ()

    def violated(self) -> bool:
        """True if any constraint is violated (hard or soft)."""
        return not (self.hard_pass and self.soft_pass)

    def worst_margin(self) -> Optional[Tuple[str, float]]:
        """Returns (name, margin) for the most negative margin, if any exist."""
        if not self.margins:
            return None
        name, margin = min(self.margins.items(), key=lambda kv: kv[1])
        return (name, float(margin))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "margins": dict(self.margins),
            "hard_pass": bool(self.hard_pass),
            "soft_pass": bool(self.soft_pass),
            "hard_violations": list(self.hard_violations),
            "soft_violations": list(self.soft_violations),
        }


@dataclass(frozen=True)
class RobustnessStats:
    """
    Optional aggregate statistics if you evaluate a candidate across multiple
    robustness/uncertainty cases.

    Planner may leave this as None if robustness was disabled.
    """

    cases: int
    hard_pass_rate: float
    soft_pass_rate: float
    mean_objective_cost: float
    max_objective_cost: float
    worst_case_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cases": int(self.cases),
            "hard_pass_rate": float(self.hard_pass_rate),
            "soft_pass_rate": float(self.soft_pass_rate),
            "mean_objective_cost": float(self.mean_objective_cost),
            "max_objective_cost": float(self.max_objective_cost),
            "worst_case_index": (
                None if self.worst_case_index is None else int(self.worst_case_index)
            ),
        }


@dataclass(frozen=True)
class Solution:
    """
    A planner output for a single best candidate.

    Fields:
    - decisions: the chosen decision variable assignment
    - plan: the constructed plan/schedule (domain-defined)
    - sim_result: the simulation output for the nominal run (domain-defined)
    - constraints: constraint evaluation summary (nominal run)
    - objective: the Objective object after evaluation (contains per-term costs)
    - score: overall scalar score used for comparison/ranking
    - robustness: optional aggregate stats across robustness cases
    - debug: optional diagnostics (iteration found, runtime, etc.)
    """

    decisions: Dict[str, Any]
    plan: Any
    sim_result: Any

    constraints: ConstraintEvaluation
    objective: Any  # kept as Any to avoid tight coupling; typically Objective
    score: float

    robustness: Optional[RobustnessStats] = None
    debug: Dict[str, Any] = field(default_factory=dict)

    def feasible(self) -> bool:
        """Feasible means all HARD constraints passed."""
        return bool(self.constraints.hard_pass)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decisions": dict(self.decisions),
            "plan": self.plan,
            "sim_result": self.sim_result,
            "constraints": self.constraints.to_dict(),
            "objective_total_cost": (
                float(self.objective.total_cost())
                if hasattr(self.objective, "total_cost")
                else None
            ),
            "score": float(self.score),
            "robustness": None if self.robustness is None else self.robustness.to_dict(),
            "debug": dict(self.debug),
        }

    def summary(self) -> str:
        """
        Human-readable one-liner-ish summary.
        Does not assume a particular sim_result schema.
        """
        obj_cost = self.objective.total_cost() if hasattr(self.objective, "total_cost") else None
        worst = self.constraints.worst_margin()
        worst_str = f"{worst[0]}={worst[1]:.3g}" if worst else "n/a"
        return (
            f"Solution(score={self.score:.6g}, "
            f"hard_pass={self.constraints.hard_pass}, "
            f"soft_pass={self.constraints.soft_pass}, "
            f"objective_cost={obj_cost}, "
            f"worst_margin={worst_str})"
        )
