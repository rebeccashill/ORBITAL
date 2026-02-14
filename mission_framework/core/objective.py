# mission_framework/core/objective.py
"""
Domain-agnostic objective / scoring system.

Design goals:
- Works for BOTH aircraft (min time/energy) and spacecraft (max science value).
- Supports simulation-in-the-loop planning (CEM / hillclimb / evolutionary).
- Clean separation from constraints:
    objective measures "goodness"
    constraints measure "allowedness" (margins)

Conventions:
- ObjectiveTerms return a scalar "cost" by default (lower is better).
- If you prefer "value" (higher is better), set is_cost=False on a term; it will be negated
  so overall objective remains "minimize total_cost".

Typical planner score:
    total_cost = objective.total_cost(sim) + penalty_weight * constraint_report.total_penalty()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np


class CombineMode(str, Enum):
    SUM = "sum"
    WEIGHTED_SUM = "weighted_sum"


@dataclass(frozen=True)
class ObjectiveTermResult:
    name: str
    raw: float                 # raw term output (cost if is_cost else value)
    cost: float                # converted to cost space (always minimized)
    weight: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectiveTerm:
    """
    Base class for one term in an objective.

    Implement evaluate(sim) -> float.

    If is_cost=True:
        term is already a cost; lower is better.
    If is_cost=False:
        term is a value; higher is better; we negate it into cost space.
    """
    name: str
    weight: float = 1.0
    is_cost: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, sim: Any) -> float:
        raise NotImplementedError

    def __call__(self, sim: Any) -> ObjectiveTermResult:
        raw = float(self.evaluate(sim))
        cost = raw if self.is_cost else -raw
        weighted_cost = float(self.weight * cost)
        return ObjectiveTermResult(
            name=self.name,
            raw=raw,
            cost=weighted_cost,
            weight=self.weight,
            metadata=dict(self.metadata),
        )


class FunctionalObjectiveTerm(ObjectiveTerm):
    """Convenience wrapper: term via a callable(sim)->float."""
    def __init__(
        self,
        name: str,
        fn: Callable[[Any], float],
        weight: float = 1.0,
        is_cost: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, weight=weight, is_cost=is_cost, metadata=metadata or {})
        self._fn = fn

    def evaluate(self, sim: Any) -> float:
        return float(self._fn(sim))


@dataclass(frozen=True)
class ObjectiveReport:
    """Breakdown of objective term contributions."""
    terms: List[ObjectiveTermResult]

    def total_cost(self) -> float:
        return float(sum(t.cost for t in self.terms))

    def by_name(self) -> Dict[str, ObjectiveTermResult]:
        return {t.name: t for t in self.terms}

    def summary(self) -> Dict[str, Any]:
        return {
            "total_cost": self.total_cost(),
            "terms": [
                {"name": t.name, "raw": t.raw, "weighted_cost": t.cost, "weight": t.weight}
                for t in self.terms
            ],
        }


@dataclass
class Objective:
    """
    An objective is a set of terms, combined into a single scalar cost to minimize.

    For spacecraft "maximize science value":
        use terms with is_cost=False (value terms) so they are negated into cost space.
    """
    terms: List[ObjectiveTerm] = field(default_factory=list)
    combine_mode: CombineMode = CombineMode.SUM

    def evaluate(self, sim: Any) -> ObjectiveReport:
        term_results: List[ObjectiveTermResult] = []
        for t in self.terms:
            term_results.append(t(sim))
        return ObjectiveReport(terms=term_results)

    def total_cost(self, sim: Any) -> float:
        report = self.evaluate(sim)
        return report.total_cost()

    def add(self, term: ObjectiveTerm) -> "Objective":
        self.terms.append(term)
        return self


# ---------------------------
# Common helper terms (optional convenience)
# ---------------------------

def term_minimize_time(name: str = "time", weight: float = 1.0, key: str = "t_end_s") -> FunctionalObjectiveTerm:
    """
    Assumes sim has an attribute or dict entry representing total time in seconds.
    """
    def _get(sim: Any) -> float:
        if hasattr(sim, key):
            return float(getattr(sim, key))
        if isinstance(sim, dict) and key in sim:
            return float(sim[key])
        raise AttributeError(f"Simulation result missing '{key}' for time objective.")
    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=True)

def term_minimize_energy(name: str = "energy", weight: float = 1.0, key: str = "energy_used_Wh") -> FunctionalObjectiveTerm:
    """
    Assumes sim has total energy used (Wh).
    """
    def _get(sim: Any) -> float:
        if hasattr(sim, key):
            return float(getattr(sim, key))
        if isinstance(sim, dict) and key in sim:
            return float(sim[key])
        raise AttributeError(f"Simulation result missing '{key}' for energy objective.")
    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=True)

def term_maximize_value(name: str = "value", weight: float = 1.0, key: str = "mission_value") -> FunctionalObjectiveTerm:
    """
    Assumes sim has a scalar mission value (higher is better).
    Will be negated into cost space.
    """
    def _get(sim: Any) -> float:
        if hasattr(sim, key):
            return float(getattr(sim, key))
        if isinstance(sim, dict) and key in sim:
            return float(sim[key])
        raise AttributeError(f"Simulation result missing '{key}' for value objective.")
    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=False)
