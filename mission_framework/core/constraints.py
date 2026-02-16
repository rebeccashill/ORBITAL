# mission_framework/core/constraints.py
"""
Domain-agnostic constraint system.

Key design choices:
- Every constraint returns a *margin* (float or array of floats):
    margin >= 0  => PASS
    margin <  0  => FAIL (violation magnitude = -margin)
- Constraints are evaluated on a SimulationResult-like object produced by your simulator.
  This keeps planning unified across aircraft + spacecraft.

Upgrades (AeroHack-focused):
- Traceability: worst index + optional worst time extraction
- Grouping: ConstraintGroup preserves per-constraint results (audit-friendly)
- Registry: ConstraintRegistry for presets and reproducible assembly
- JSON exports: report/results are easy to dump to /outputs for validation bundles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

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
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def min_margin(self) -> float:
        return float(np.min(self.margins)) if self.margins.size else float("inf")

    @property
    def is_satisfied(self) -> bool:
        return self.min_margin >= 0.0

    @property
    def max_violation(self) -> float:
        return float(max(0.0, -self.min_margin))

    @property
    def worst_index(self) -> Optional[int]:
        """Index of the worst (minimum) margin, if margins are non-empty."""
        if self.margins.size == 0:
            return None
        return int(np.argmin(self.margins))

    def worst_time(self) -> Optional[float]:
        """
        If metadata contains a 1D 't' array aligned with margins, return time at worst index.
        Convention: simulator outputs can attach metadata={'t': sim.t} in the constraint.
        """
        idx = self.worst_index
        if idx is None:
            return None
        t = self.metadata.get("t", None)
        if t is None or callable(t):
            return None
        try:
            t_arr = np.asarray(t, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            return None
        if idx < 0 or idx >= t_arr.size:
            return None
        return float(t_arr[idx])

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
        Default: sum of squared violations.
        """
        v = np.maximum(0.0, -self.margins)
        return float(self.weight * np.sum(v * v))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly summary for results bundles."""
        return {
            "name": self.name,
            "severity": str(self.severity.value),
            "reduce_mode": str(self.reduce_mode.value),
            "weight": float(self.weight),
            "is_satisfied": bool(self.is_satisfied),
            "min_margin": float(self.min_margin),
            "max_violation": float(self.max_violation),
            "worst_index": self.worst_index,
            "worst_time": self.worst_time(),
            # keep metadata but make it safer to serialize (avoid huge arrays)
            "metadata_keys": sorted(list(self.metadata.keys())),
        }


@dataclass(frozen=True)
class ConstraintReport:
    """Aggregated constraint evaluation results."""
    results: List[ConstraintResult]

    @property
    def hard_pass(self) -> bool:
        return all(r.is_satisfied for r in self.results if r.severity == Severity.HARD)

    @property
    def soft_pass(self) -> bool:
        return all(r.is_satisfied for r in self.results if r.severity == Severity.SOFT)

    def by_name(self) -> Dict[str, ConstraintResult]:
        return {r.name: r for r in self.results}

    def worst(self, severity: Optional[Severity] = None) -> Optional[ConstraintResult]:
        candidates = self.results if severity is None else [r for r in self.results if r.severity == severity]
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.min_margin)

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
            "worst_hard": None if worst_hard is None else worst_hard.to_dict(),
            "worst_soft": None if worst_soft is None else worst_soft.to_dict(),
        }

    def to_jsonable(self) -> Dict[str, Any]:
        """Full JSON-friendly report (for /outputs/constraint_report.json)."""
        return {
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------
# Constraint interface
# ---------------------------

class Constraint:
    """
    Base constraint. Implementations must define evaluate(sim) -> np.ndarray margins.
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
    """Define a constraint with a callable(sim) -> margin(s)."""
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
    Backwards-compatible: groups multiple constraints into ONE combined margin vector.
    Good for “single score”, bad for audits (use ConstraintGroup for audits).
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


class ConstraintGroup:
    """
    Audit-friendly container: preserves child results (does NOT merge them).
    Evaluate via evaluate_constraints(...), which flattens groups automatically.
    """
    def __init__(self, name: str, constraints: Sequence[Union[Constraint, "ConstraintGroup"]]):
        self.name = name
        self.constraints = list(constraints)


# ---------------------------
# Registry (presets)
# ---------------------------

class ConstraintRegistry:
    """
    Simple registry for reproducible constraint bundles.
    Use this to expose 'aircraft_baseline', 'spacecraft_baseline', etc.
    """
    def __init__(self):
        self._builders: Dict[str, Callable[..., Sequence[Union[Constraint, ConstraintGroup]]]] = {}

    def register(self, key: str, builder: Callable[..., Sequence[Union[Constraint, ConstraintGroup]]]) -> None:
        if key in self._builders:
            raise KeyError(f"Constraint preset already registered: {key}")
        self._builders[key] = builder

    def build(self, key: str, **kwargs: Any) -> List[Union[Constraint, ConstraintGroup]]:
        if key not in self._builders:
            raise KeyError(f"Unknown constraint preset: {key}. Available: {sorted(self._builders.keys())}")
        built = self._builders[key](**kwargs)
        return list(built)

    def keys(self) -> List[str]:
        return sorted(self._builders.keys())


# ---------------------------
# Evaluation helpers
# ---------------------------

def _flatten_constraints(items: Sequence[Union[Constraint, ConstraintGroup]]) -> List[Constraint]:
    flat: List[Constraint] = []
    for it in items:
        if isinstance(it, Constraint):
            flat.append(it)
        elif isinstance(it, ConstraintGroup):
            flat.extend(_flatten_constraints(it.constraints))
        else:
            raise TypeError(f"Unknown constraint container type: {type(it)}")
    return flat


def evaluate_constraints(sim: Any, constraints: Sequence[Union[Constraint, ConstraintGroup]]) -> ConstraintReport:
    """
    Evaluate all constraints on the simulation output/context.
    Flattens nested ConstraintGroup containers automatically.
    Returns one ConstraintResult per *Constraint* (groups are just containers).
    """
    results: List[ConstraintResult] = []
    for c in _flatten_constraints(constraints):
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
        f"min_margin={worst.min_margin:.6g}, max_violation={worst.max_violation:.6g}, "
        f"worst_index={worst.worst_index}, worst_time={worst.worst_time()}"
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