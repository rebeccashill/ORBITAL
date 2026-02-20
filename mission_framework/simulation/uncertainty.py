# mission_framework/simulation/uncertainty.py
"""
Monte Carlo / parameter variation utilities.

This module provides a unified way to:
- Define uncertainty cases (random seeds + parameter overrides)
- Run a plan under those cases
- Summarize feasibility + performance distributions

Key principle:
- The planner stays domain-agnostic.
- The simulator stays domain-agnostic.
- Uncertainty is injected through a domain-provided "apply_case" hook.

You can use this for:
- Aircraft: wind seed, wind scale, mass variation, energy rate variation
- Spacecraft: battery capacity variation, pointing rate variation, contact timing jitter

Typical usage:
    cases = make_seed_cases(50, seed0=0)
    # or parameter sweeps:
    cases = [
        UncertaintyCase(seed=0, params={"wind_scale": 0.8}),
        UncertaintyCase(seed=1, params={"wind_scale": 1.2}),
    ]

    runner = UncertaintyRunner(simulate_fn, apply_case_fn)
    results = runner.run(plan, cases)

    summary = summarize_uncertainty(results, metrics_fn=...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from mission_framework.core.constraints import (
    Constraint,
    ConstraintReport,
    Severity,
    evaluate_constraints,
)
from mission_framework.core.objective import Objective, ObjectiveReport
from mission_framework.core.types import Plan, SimResult

# ---------------------------
# Case definition
# ---------------------------


@dataclass(frozen=True)
class UncertaintyCase:
    """
    One Monte Carlo / variation case.

    - seed: RNG seed for stochastic elements (wind draw, noise, jitter)
    - params: optional parameter overrides (domain-defined)
    """

    seed: int
    params: Dict[str, Any] = field(default_factory=dict)


def make_seed_cases(n: int, seed0: int = 0, stride: int = 10007) -> List[UncertaintyCase]:
    """Deterministic list of pure-seed cases."""
    return [UncertaintyCase(seed=int(seed0 + i * stride), params={}) for i in range(int(n))]


# ---------------------------
# Runner
# ---------------------------

SimulateFn = Callable[[Plan, Optional[np.random.Generator]], SimResult]
ApplyCaseFn = Callable[[Plan, Dict[str, Any]], Plan]


@dataclass
class UncertaintyRunner:
    """
    Runs a plan under multiple uncertainty cases.

    You provide:
    - simulate_fn(plan, rng) -> SimResult     (domain sim)
    - apply_case_fn(plan, params) -> Plan    (domain hook to override params)
        If you don't need param overrides, you can omit apply_case_fn and only use seeds.
    """

    simulate_fn: SimulateFn
    apply_case_fn: Optional[ApplyCaseFn] = None

    def run(self, plan: Plan, cases: Sequence[UncertaintyCase]) -> List[SimResult]:
        out: List[SimResult] = []
        for c in cases:
            rng = np.random.default_rng(int(c.seed))
            p = plan
            if self.apply_case_fn is not None and c.params:
                p = self.apply_case_fn(plan, c.params)
            sim = self.simulate_fn(p, rng)
            out.append(sim)
        return out


# ---------------------------
# Evaluation (constraints + objective) across cases
# ---------------------------


@dataclass(frozen=True)
class CaseEvaluation:
    case: UncertaintyCase
    sim: SimResult
    constraints: Optional[ConstraintReport] = None
    objective: Optional[ObjectiveReport] = None
    score: Optional[float] = (
        None  # objective_cost + penalty_weight*penalty (+ optional hard fail penalty)
    )


def evaluate_cases(
    cases: Sequence[UncertaintyCase],
    sims: Sequence[SimResult],
    constraints: Optional[Sequence[Constraint]] = None,
    objective: Optional[Objective] = None,
    penalty_weight: float = 1000.0,
    hard_infeasible_penalty: float = 1e6,
) -> List[CaseEvaluation]:
    """
    Evaluate constraint feasibility and objective cost across uncertainty cases.

    Returns per-case evaluations with a comparable scalar score.
    """
    if len(cases) != len(sims):
        raise ValueError("cases and sims must be the same length.")

    out: List[CaseEvaluation] = []

    for c, sim in zip(cases, sims):
        crep = evaluate_constraints(sim, constraints) if constraints is not None else None
        orep = objective.evaluate(sim) if objective is not None else None

        score = None
        if crep is not None and orep is not None:
            obj_cost = float(orep.total_cost())
            penalty = float(crep.total_penalty(include_hard=True, include_soft=True))
            score = obj_cost + penalty_weight * penalty
            if not crep.hard_pass:
                score += float(hard_infeasible_penalty)

        out.append(CaseEvaluation(case=c, sim=sim, constraints=crep, objective=orep, score=score))

    return out


# ---------------------------
# Summary statistics
# ---------------------------


def summarize_uncertainty(evals: Sequence[CaseEvaluation]) -> Dict[str, Any]:
    """
    Summarize feasibility + score distribution.

    Assumes constraints/objective were evaluated (score present).
    """
    scores = [e.score for e in evals if e.score is not None]
    scores_np = np.array(scores, dtype=float) if scores else None

    hard_pass = [bool(e.constraints.hard_pass) for e in evals if e.constraints is not None]
    hard_pass_rate = float(np.mean(np.array(hard_pass, dtype=float))) if hard_pass else None

    worst_hard_margins: List[float] = []
    for e in evals:
        if e.constraints is None:
            continue
        w = e.constraints.worst(Severity.HARD)
        worst_hard_margins.append(float(w.min_margin) if w is not None else float("inf"))

    out: Dict[str, Any] = {
        "cases": len(evals),
        "hard_pass_rate": hard_pass_rate,
        "worst_hard_margin_min": (
            float(np.min(np.array(worst_hard_margins, dtype=float))) if worst_hard_margins else None
        ),
    }

    if scores_np is not None and scores_np.size > 0:
        out.update(
            {
                "mean_score": float(np.mean(scores_np)),
                "p50_score": float(np.percentile(scores_np, 50)),
                "p90_score": float(np.percentile(scores_np, 90)),
                "min_score": float(np.min(scores_np)),
                "max_score": float(np.max(scores_np)),
            }
        )

    return out


# ---------------------------
# Parameter sweep helper
# ---------------------------


def make_param_sweep(
    base_seed: int,
    name: str,
    values: Sequence[Any],
    seed_stride: int = 10007,
) -> List[UncertaintyCase]:
    """
    Create cases that sweep one parameter.

    Example:
        cases = make_param_sweep(0, "wind_scale", [0.8, 1.0, 1.2])
    """
    out: List[UncertaintyCase] = []
    for i, v in enumerate(values):
        out.append(UncertaintyCase(seed=int(base_seed + i * seed_stride), params={name: v}))
    return out
