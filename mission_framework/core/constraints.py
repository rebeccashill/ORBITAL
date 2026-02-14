# mission_framework/core/constraints.py
"""
Domain-agnostic constraint system.

Key design choices (hackathon + "SpaceX-style" verification):
- Every constraint returns a *margin* (float or array of floats):
    margin >= 0  => PASS
    margin <  0  => FAIL (violation magnitude = -margin)
- Constraints are evaluated on a SimulationResult-like object produced by your simulator.
  This keeps planning unified across aircraft + spacecraft.

This module does NOT assume what "state" is.
It only assumes the simulator returns a context object (any Python object)
that constraints can read.

Typical usage:
    constraints = [
        ConstraintSet(...),
        ...
    ]
    report = evaluate_constraints(sim_result, constraints)
    penalty = report.total_penalty()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np


# ---------------------------
# Core types
# ---------------------------

class Severity(str, Enum):
    HARD = "hard"   # must satisfy (feasibility)
    SOFT = "soft"   # may violate but penalized


class ReduceMode(str, Enum):
    """How to reduce an array of margins to a single scalar summary."""
    MIN = "min"           # most common for safety constraints
    MEAN = "mean"
    SUM_NEG = "sum_neg"   # sum of violations only (useful for penalties)
    COUNT_NEG = "count_neg"


@dataclass(frozen=True)
class ConstraintResult:
    """Result of evaluating a single constraint."""
    name: str
    severity: Severity
    margins: np.ndarray  # shape (K,) or (1,)
    reduce_mode: ReduceMode = ReduceMode.MIN
    weight: float = 1.0  # penalty weight (used when severity=SOFT or for hard penalties in scoring)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def min_margin(self) -> float:
        return float(np.min(self.margins)) if self.margins.size else float("inf")

    @property
    def is_satisfied(self) -> bool:
        return self.min_margin >= 0.0

    @property
    def max_violation(self) -> float:
        # violation is positive number (0 means no violation)
        return float(max(0.0, -self.min_margin))

    def reduced(self) -> float:
        m = self.margins
        if m.size == 0:
            return float("inf")
        if self.reduce_mode == ReduceMode.MIN:
            return float(np.min(m))
        if self.reduce_mode == ReduceMode.MEAN:
            return float(np.mean(m))
        if self.reduce_mode == ReduceMode.SUM_NEG:
            return float(np.sum(np.minimum(m, 0.0)))
        if self.reduce_mode == ReduceMode.COUNT_NEG:
            return float(np.sum(m < 0.0))
        raise ValueError(f"Unknown ReduceMode: {self.reduce_mode}")

    def penalty(self) -> float:
        """
        Penalty computed from violations.
        - For HARD constraints, this can still be used in "repair / scoring" mode,
          but feasibility should be assessed separately via is_satisfied.
        """
        # Use a smooth-ish penalty: sum of squared violations (common hackathon default)
        v = np.maximum(0.0, -self.margins)
        return float(self.weight * np.sum(v * v))


@dataclass(frozen=True)
class ConstraintReport:
    """Aggregated constraint evaluation results."""
    results: List[ConstraintResult]

    @property
    def hard_pass(self) -> bool:
        return all(r.is_satisfied for r in self.results if r.severity == Severity.HARD)

    @property
    def soft_pass(self) -> bool:
        # soft constraints can violate; "pass" means none violated
        return all(r.is_satisfied for r in self.results if r.severity == Severity.SOFT)

    def by_name(self) -> Dict[str, ConstraintResult]:
        return {r.name: r for r in self.results}

    def worst(self, severity: Optional[Severity] = None) -> Optional[ConstraintResult]:
        candidates = self.results if severity is None else [r for r in self.results if r.severity == severity]
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.min_margin)  # smallest margin = worst

    def total_penalty(self, include_hard: bool = True, include_soft: bool = True) -> float:
        tot = 0.0
        for r in self.results:
            if r.severity == Severity.HARD and not include_hard:
                continue
            if r.severity == Severity.SOFT and not include_soft:
                continue
            tot += r.penalty()
        return float(tot)

    def summary(self) -> Dict[str, Any]:
        worst_hard = self.worst(Severity.HARD)
        worst_soft = self.worst(Severity.SOFT)
        return {
            "hard_pass": self.hard_pass,
            "soft_pass": self.soft_pass,
            "total_penalty": self.total_penalty(),
            "worst_hard": None if worst_hard is None else {
                "name": worst_hard.name,
                "min_margin": worst_hard.min_margin,
                "max_violation": worst_hard.max_violation,
            },
            "worst_soft": None if worst_soft is None else {
                "name": worst_soft.name,
                "min_margin": worst_soft.min_margin,
                "max_violation": worst_soft.max_violation,
            },
        }


# ---------------------------
# Constraint interface
# ---------------------------

class Constraint:
    """
    Base constraint.

    Implementations must define evaluate(sim) -> np.ndarray margins.
    """
    name: str
    severity: Severity
    weight: float
    reduce_mode: ReduceMode
    metadata: Dict[str, Any]

    def __init__(
        self,
        name: str,
        severity: Severity = Severity.HARD,
        weight: float = 1.0,
        reduce_mode: ReduceMode = ReduceMode.MIN,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.severity = severity
        self.weight = float(weight)
        self.reduce_mode = reduce_mode
        self.metadata = metadata or {}

    def evaluate(self, sim: Any) -> np.ndarray:
        """Return margin array. Must be overridden."""
        raise NotImplementedError

    def __call__(self, sim: Any) -> ConstraintResult:
        margins = np.array(self.evaluate(sim), dtype=float).reshape(-1)
        return ConstraintResult(
            name=self.name,
            severity=self.severity,
            margins=margins,
            reduce_mode=self.reduce_mode,
            weight=self.weight,
            metadata=dict(self.metadata),
        )


class FunctionalConstraint(Constraint):
    """
    Convenience wrapper: define a constraint with a callable(sim) -> margin(s).

    Example:
        c = FunctionalConstraint(
            "battery_nonnegative",
            fn=lambda sim: sim.battery_Wh,   # margin = battery_Wh >= 0
        )
    """
    def __init__(
        self,
        name: str,
        fn: Callable[[Any], Union[float, Sequence[float], np.ndarray]],
        severity: Severity = Severity.HARD,
        weight: float = 1.0,
        reduce_mode: ReduceMode = ReduceMode.MIN,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name, severity=severity, weight=weight, reduce_mode=reduce_mode, metadata=metadata)
        self._fn = fn

    def evaluate(self, sim: Any) -> np.ndarray:
        return np.array(self._fn(sim), dtype=float)


class ConstraintSet(Constraint):
    """
    Groups multiple constraints together (for organization only).

    evaluate(sim) returns a concatenated margin vector.

    Note: A ConstraintSet produces ONE ConstraintResult with combined margins.
    If you want individual results, pass the children directly into evaluate_constraints.
    """
    def __init__(
        self,
        name: str,
        constraints: Sequence[Constraint],
        severity: Severity = Severity.HARD,
        weight: float = 1.0,
        reduce_mode: ReduceMode = ReduceMode.MIN,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name, severity=severity, weight=weight, reduce_mode=reduce_mode, metadata=metadata)
        self.constraints = list(constraints)

    def evaluate(self, sim: Any) -> np.ndarray:
        parts = []
        for c in self.constraints:
            r = c(sim)
            parts.append(r.margins)
        return np.concatenate(parts) if parts else np.array([], dtype=float)


# ---------------------------
# Evaluation helpers
# ---------------------------

def evaluate_constraints(sim: Any, constraints: Sequence[Constraint]) -> ConstraintReport:
    """
    Evaluate all constraints on the simulation output/context.

    Returns a ConstraintReport with one ConstraintResult per constraint in the list.
    """
    results: List[ConstraintResult] = []
    for c in constraints:
        results.append(c(sim))
    return ConstraintReport(results=results)


def require_hard_feasible(report: ConstraintReport, error_prefix: str = "Infeasible plan") -> None:
    """Raise a ValueError if any HARD constraint is violated (useful in tests)."""
    if report.hard_pass:
        return
    worst = report.worst(Severity.HARD)
    if worst is None:
        raise ValueError(f"{error_prefix}: hard constraints failed (unknown worst).")
    raise ValueError(
        f"{error_prefix}: hard constraint '{worst.name}' violated. "
        f"min_margin={worst.min_margin:.6g}, max_violation={worst.max_violation:.6g}"
    )


# ---------------------------
# Common margin utilities
# ---------------------------

def margin_leq(x: Union[float, np.ndarray], limit: float) -> np.ndarray:
    """Constraint x <= limit  => margin = limit - x."""
    return np.array(limit - np.array(x, dtype=float), dtype=float)

def margin_geq(x: Union[float, np.ndarray], limit: float) -> np.ndarray:
    """Constraint x >= limit  => margin = x - limit."""
    return np.array(np.array(x, dtype=float) - limit, dtype=float)

def margin_in_range(x: Union[float, np.ndarray], low: float, high: float) -> np.ndarray:
    """Constraint low <= x <= high => margins for both sides concatenated."""
    xarr = np.array(x, dtype=float)
    return np.concatenate([margin_geq(xarr, low).reshape(-1), margin_leq(xarr, high).reshape(-1)])

def margin_nonnegative(x: Union[float, np.ndarray]) -> np.ndarray:
    """Constraint x >= 0 => margin = x."""
    return np.array(x, dtype=float)
