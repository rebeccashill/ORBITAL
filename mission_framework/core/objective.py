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
    score = objective_cost + penalty_weight * constraint_penalty + extra_penalties

AeroHack additions:
- Explicit scoring config and report objects (auditability)
- Robust aggregation across Monte-Carlo seeds (mean/worst/CVaR)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np


class CombineMode(str, Enum):
    SUM = "sum"
    WEIGHTED_SUM = "weighted_sum"


@dataclass(frozen=True)
class ObjectiveTermResult:
    name: str
    raw: float  # raw term output (cost if is_cost else value)
    cost: float  # converted to weighted cost space (always minimized)
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

    def to_jsonable(self) -> Dict[str, Any]:
        return self.summary()


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
# Scoring: objective + constraints + robustness
# ---------------------------


class RobustAggregation(str, Enum):
    MEAN = "mean"
    WORST = "worst"
    CVAR = "cvar"  # Conditional Value at Risk (upper tail of cost)


@dataclass(frozen=True)
class ScoreConfig:
    """
    Defines how to compute a single scalar score the planner minimizes.
    """

    penalty_weight: float = 1000.0  # multiply constraint penalty
    include_hard: bool = True  # include HARD penalties
    include_soft: bool = True  # include SOFT penalties

    # Optional: discourage "barely feasible" solutions by rewarding margins.
    # Example: if margin_reward_weight > 0, then larger min margins reduce score slightly.
    margin_reward_weight: float = 0.0

    # Robust scoring config
    robust_aggregation: RobustAggregation = RobustAggregation.MEAN
    cvar_alpha: float = 0.8  # CVaR over worst (1-alpha) tail, e.g. alpha=0.8 => worst 20%


@dataclass(frozen=True)
class ScoreReport:
    """
    Single-run score breakdown (objective + constraints + extras).
    """

    objective: ObjectiveReport
    objective_cost: float
    constraint_penalty: float
    constraint_margin_reward: float
    total_score: float
    constraint_summary: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "total_score": float(self.total_score),
            "objective_cost": float(self.objective_cost),
            "constraint_penalty": float(self.constraint_penalty),
            "constraint_margin_reward": float(self.constraint_margin_reward),
            "objective": self.objective.to_jsonable(),
            "constraint_summary": self.constraint_summary,
            "metadata": dict(self.metadata),
        }


def score_plan(
    sim: Any,
    objective: Objective,
    constraint_report: Optional[Any] = None,
    config: ScoreConfig = ScoreConfig(),
    extra_penalties: Optional[Sequence[Callable[[Any], float]]] = None,
) -> ScoreReport:
    """
    Compute scalar score for a single simulation.
    This is what your planner should minimize.

    constraint_report is expected to be your core/constraints.ConstraintReport
    (kept as Any to avoid circular import).
    """
    obj_rep = objective.evaluate(sim)
    obj_cost = obj_rep.total_cost()

    c_pen = 0.0
    c_sum = None
    margin_reward = 0.0

    if constraint_report is not None:
        # Your ConstraintReport already exposes total_penalty() and summary() in the upgraded version.
        # If you're using the earlier version, implement those or adapt here.
        if hasattr(constraint_report, "total_penalty"):
            c_pen = float(
                constraint_report.total_penalty(
                    include_hard=config.include_hard, include_soft=config.include_soft
                )
            )
        else:
            # fallback: try generic attribute
            c_pen = float(getattr(constraint_report, "penalty", 0.0))

        if hasattr(constraint_report, "summary"):
            c_sum = constraint_report.summary()

        if config.margin_reward_weight != 0.0:
            # Reward feasibility margin: use worst HARD min_margin if available, else worst overall.
            worst = None
            if hasattr(constraint_report, "worst"):
                worst = constraint_report.worst()  # worst overall
            if worst is not None and hasattr(worst, "min_margin"):
                # If min_margin positive, subtract (reward). If negative, no reward.
                m = float(worst.min_margin)
                if m > 0.0:
                    margin_reward = -config.margin_reward_weight * m

    extras = 0.0
    if extra_penalties:
        for fn in extra_penalties:
            extras += float(fn(sim))

    total = float(obj_cost + config.penalty_weight * c_pen + margin_reward + extras)

    return ScoreReport(
        objective=obj_rep,
        objective_cost=float(obj_cost),
        constraint_penalty=float(c_pen),
        constraint_margin_reward=float(margin_reward),
        total_score=total,
        constraint_summary=c_sum,
        metadata={"extras": float(extras), "penalty_weight": float(config.penalty_weight)},
    )


@dataclass(frozen=True)
class RobustScoreReport:
    """
    Robust aggregation over multiple simulations (Monte-Carlo seeds / uncertainty draws).
    """

    aggregated_score: float
    per_run_scores: List[float]
    aggregation: RobustAggregation
    alpha: Optional[float] = None
    per_run_reports: Optional[List[ScoreReport]] = None

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "aggregated_score": float(self.aggregated_score),
            "aggregation": str(self.aggregation.value),
            "alpha": None if self.alpha is None else float(self.alpha),
            "per_run_scores": [float(x) for x in self.per_run_scores],
        }


def score_robust(
    sims: Sequence[Any],
    objective: Objective,
    constraint_reports: Optional[Sequence[Any]] = None,
    config: ScoreConfig = ScoreConfig(),
    extra_penalties: Optional[Sequence[Callable[[Any], float]]] = None,
    keep_reports: bool = False,
) -> RobustScoreReport:
    """
    Score many simulations and robustly aggregate them.

    Typical usage for AeroHack:
    - run N wind seeds for the same planned mission
    - compute N scores
    - aggregate via MEAN or CVAR (risk-aware)

    constraint_reports can be provided per sim; if None, constraints are skipped.
    """
    if constraint_reports is not None and len(constraint_reports) != len(sims):
        raise ValueError("constraint_reports must be same length as sims (or None).")

    per_scores: List[float] = []
    per_reports: List[ScoreReport] = []

    for i, sim in enumerate(sims):
        cr = None if constraint_reports is None else constraint_reports[i]
        rep = score_plan(sim, objective, cr, config=config, extra_penalties=extra_penalties)
        per_scores.append(float(rep.total_score))
        if keep_reports:
            per_reports.append(rep)

    x = np.asarray(per_scores, dtype=float)

    if config.robust_aggregation == RobustAggregation.MEAN:
        agg = float(np.mean(x)) if x.size else float("inf")
        return RobustScoreReport(
            aggregated_score=agg,
            per_run_scores=per_scores,
            aggregation=config.robust_aggregation,
            alpha=None,
            per_run_reports=per_reports if keep_reports else None,
        )

    if config.robust_aggregation == RobustAggregation.WORST:
        agg = float(np.max(x)) if x.size else float("inf")
        return RobustScoreReport(
            aggregated_score=agg,
            per_run_scores=per_scores,
            aggregation=config.robust_aggregation,
            alpha=None,
            per_run_reports=per_reports if keep_reports else None,
        )

    if config.robust_aggregation == RobustAggregation.CVAR:
        alpha = float(config.cvar_alpha)
        if not (0.0 < alpha < 1.0):
            raise ValueError("cvar_alpha must be in (0,1).")
        if x.size == 0:
            agg = float("inf")
        else:
            # CVaR on cost => average of worst (1-alpha) tail
            q = np.quantile(x, alpha)
            tail = x[x >= q]
            agg = float(np.mean(tail)) if tail.size else float(np.max(x))
        return RobustScoreReport(
            aggregated_score=agg,
            per_run_scores=per_scores,
            aggregation=config.robust_aggregation,
            alpha=alpha,
            per_run_reports=per_reports if keep_reports else None,
        )

    raise ValueError(f"Unknown RobustAggregation: {config.robust_aggregation}")


# ---------------------------
# Internal scalar getter
# ---------------------------


def _get_scalar(sim: Any, key: str) -> Optional[float]:
    """
    Try to read a scalar value from common locations:
    1) attribute: sim.<key>
    2) SimResult-like: sim.scalars[<key>]
    3) dict: sim[<key>]
    Returns None if not found.
    """
    if hasattr(sim, key):
        try:
            return float(getattr(sim, key))
        except Exception:
            pass

    if hasattr(sim, "scalars"):
        scalars = getattr(sim, "scalars", None)
        if isinstance(scalars, dict) and key in scalars:
            return float(scalars[key])

    if isinstance(sim, dict) and key in sim:
        return float(sim[key])

    return None


# ---------------------------
# Common helper terms (optional convenience)
# ---------------------------


def term_minimize_time(
    name: str = "time", weight: float = 1.0, key: str = "t_end_s"
) -> FunctionalObjectiveTerm:
    """
    Assumes sim exposes total time in seconds.
    Supports SimResult.scalars[key] (preferred), attribute, or dict.
    """

    def _get(sim: Any) -> float:
        v = _get_scalar(sim, key)
        if v is None:
            raise AttributeError(f"Simulation result missing '{key}' for time objective.")
        return v

    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=True)


def term_minimize_energy(
    name: str = "energy", weight: float = 1.0, key: str = "energy_used_Wh"
) -> FunctionalObjectiveTerm:
    """
    Assumes sim exposes total energy used (Wh).
    Supports SimResult.scalars[key] (preferred), attribute, or dict.
    """

    def _get(sim: Any) -> float:
        v = _get_scalar(sim, key)
        if v is None:
            raise AttributeError(f"Simulation result missing '{key}' for energy objective.")
        return v

    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=True)


def term_maximize_value(
    name: str = "value", weight: float = 1.0, key: str = "mission_value"
) -> FunctionalObjectiveTerm:
    """
    Assumes sim exposes mission value (higher is better).
    Supports SimResult.scalars[key] (preferred), attribute, or dict.
    Negated into cost space.
    """

    def _get(sim: Any) -> float:
        v = _get_scalar(sim, key)
        if v is None:
            raise AttributeError(f"Simulation result missing '{key}' for value objective.")
        return v

    return FunctionalObjectiveTerm(name=name, fn=_get, weight=weight, is_cost=False)
