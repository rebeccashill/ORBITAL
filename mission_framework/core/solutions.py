"""Solution containers for Orbital planners."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

from mission_framework.core.constraints import ConstraintReport, Severity
from mission_framework.core.decision_variables import DecisionAssignment
from mission_framework.core.objective import ObjectiveReport, ScoreReport


@dataclass
class PlanResult:
    """Canonical output returned by planners."""

    assignment: DecisionAssignment
    plan: Any
    sim_result: Any
    constraints: ConstraintReport
    score_report: ScoreReport
    score: float
    robustness: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def decisions(self) -> Dict[str, Any]:
        """Expose raw decision values for callers that prefer dictionary access."""
        return self.assignment.values

    @property
    def objective(self) -> ObjectiveReport:
        """Backward-compatible access to the evaluated objective report."""
        return self.score_report.objective

    def feasible(self) -> bool:
        """Feasible means all hard constraints passed."""
        return bool(self.constraints.hard_pass)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation of the result."""
        return {
            "decisions": _to_builtin(self.assignment.values),
            "plan": _to_builtin(self.plan),
            "sim_result": _to_builtin(self.sim_result),
            "constraints": _to_builtin(
                self.constraints.to_jsonable()
                if hasattr(self.constraints, "to_jsonable")
                else self.constraints.summary()
            ),
            "score_report": _to_builtin(self.score_report.to_jsonable()),
            "objective": _to_builtin(self.objective.summary()),
            "score": float(self.score),
            "robustness": _to_builtin(self.robustness),
            "history": _to_builtin(self.history),
            "debug": _to_builtin(self.debug),
        }

    def summary(self) -> str:
        """Human-readable one-line summary for logs and CLIs."""
        worst = self.constraints.worst(Severity.HARD)
        worst_str = "n/a" if worst is None else f"{worst.name}={worst.min_margin:.3g}"
        return (
            f"PlanResult(score={self.score:.6g}, "
            f"hard_pass={self.constraints.hard_pass}, "
            f"objective_cost={self.objective.total_cost():.6g}, "
            f"worst_hard_margin={worst_str})"
        )

    def to_jsonable(self) -> Dict[str, Any]:
        """Alias used by reporting code that expects JSON-ready objects."""
        return self.to_dict()


def _to_builtin(value: Any) -> Any:
    """Convert common scientific Python values into JSON-friendly types."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(v) for v in value]
    if is_dataclass(value):
        return _to_builtin(asdict(value))
    return value


# Compatibility name for early code that imported Solution from this module.
Solution = PlanResult
