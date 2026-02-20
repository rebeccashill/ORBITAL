# mission_framework/core/planner.py
"""
Single unified planning method: Simulation-in-the-loop stochastic optimization.

Planner objective (minimize):
    total_score = objective_cost
                + penalty_weight * constraint_penalty
                + optional extras (margin reward / custom penalties)

Why this planner:
- Works for BOTH aircraft (route/timing/control) and spacecraft (7-day scheduling).
- Handles mixed decision variables (continuous/integer/binary/permutation) without MILP pain.
- Naturally supports robustness: evaluate candidates across multiple uncertainty cases.

This file is intentionally domain-agnostic:
- Domain provides build_plan() and simulate()
- Constraints + Objective are shared interfaces
- One optimization loop across both domains
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from mission_framework.core.decision_variables import (
    DecisionAssignment,
    DecisionSpace,
    MutationConfig,
)
from mission_framework.core.constraints import (
    Constraint,
    ConstraintGroup,
    ConstraintReport,
    Severity,
    evaluate_constraints,
)
from mission_framework.core.objective import (
    Objective,
    ScoreConfig,
    ScoreReport,
    RobustScoreReport,
    score_plan,
    score_robust,
    RobustAggregation,
)

# ---------------------------
# Problem / Solution interfaces
# ---------------------------


@dataclass
class Problem:
    """
    Domain-agnostic wrapper that connects:
    - decision space
    - decoding decisions -> executable plan
    - simulation of that plan
    - constraints and objective
    """

    decision_space: DecisionSpace
    build_plan: Callable[[DecisionAssignment], Any]  # decisions -> plan object
    simulate: Callable[[Any, Optional[np.random.Generator]], Any]  # (plan, rng) -> sim_result
    constraints: List[Union[Constraint, ConstraintGroup]]
    objective: Objective

    # Robustness evaluation (optional)
    robustness_cases: int = 0
    robustness_seeds: Optional[List[int]] = None

    # Optional: robust aggregation selection (defaults chosen to look strong in AeroHack)
    robust_aggregation: RobustAggregation = RobustAggregation.CVAR
    cvar_alpha: float = 0.8  # worst 20%

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    """
    What the planner returns.
    Report-heavy, hackathon friendly.
    """

    assignment: DecisionAssignment
    plan: Any
    sim_result: Any
    constraints: ConstraintReport
    score_report: ScoreReport
    score: float

    # Robustness summary (if used)
    robustness: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None


# ---------------------------
# Planner config
# ---------------------------


@dataclass
class PlannerConfig:
    iterations: int = 2000
    restarts: int = 5

    # Mutation tuning
    mutation: MutationConfig = field(default_factory=MutationConfig)
    intensity_start: float = 1.0
    intensity_end: float = 0.2  # anneal mutation magnitude over time

    # Scoring config (unified with objective.py)
    scoring: ScoreConfig = field(
        default_factory=lambda: ScoreConfig(
            penalty_weight=1000.0,
            include_hard=True,
            include_soft=True,
            margin_reward_weight=0.0,
            robust_aggregation=RobustAggregation.MEAN,  # overridden per-problem if robustness enabled
            cvar_alpha=0.8,
        )
    )

    # Extra penalty if any hard constraint fails (useful for guiding search)
    hard_infeasible_penalty: float = 1e6

    # Acceptance policy
    accept_worse_prob: float = 0.0
    accept_worse_temp: float = 1.0

    # Early stopping
    stop_if_feasible_for: int = 0

    # Reproducibility
    seed: int = 0

    # Logging
    keep_history: bool = True
    history_stride: int = 1


# ---------------------------
# Core planner
# ---------------------------


class Planner:
    def __init__(self, cfg: PlannerConfig = PlannerConfig()):
        self.cfg = cfg

    def solve(self, problem: Problem) -> PlanResult:
        rng_master = np.random.default_rng(self.cfg.seed)
        best_global: Optional[PlanResult] = None

        for r in range(self.cfg.restarts):
            seed_r = int(rng_master.integers(0, 2**31 - 1))
            rng = np.random.default_rng(seed_r)

            # Initial candidate
            current = problem.decision_space.random_feasible(seed=int(rng.integers(0, 2**31 - 1)))
            best_local = self._evaluate(problem, current, rng)

            history: List[Dict[str, Any]] = []
            feasible_streak = 0

            for it in range(self.cfg.iterations):
                intensity = self._anneal(
                    it, self.cfg.iterations, self.cfg.intensity_start, self.cfg.intensity_end
                )
                cand = problem.decision_space.mutate(
                    best_local.assignment, rng=rng, cfg=self.cfg.mutation, intensity=intensity
                )

                cand_eval = self._evaluate(problem, cand, rng)

                if self._accept(cand_eval.score, best_local.score, rng):
                    best_local = cand_eval

                if best_local.constraints.hard_pass:
                    feasible_streak += 1
                else:
                    feasible_streak = 0

                if self.cfg.keep_history and (it % max(1, self.cfg.history_stride) == 0):
                    worst_h = best_local.constraints.worst(Severity.HARD)
                    history.append(
                        {
                            "restart": r,
                            "iter": it,
                            "best_score": float(best_local.score),
                            "hard_pass": bool(best_local.constraints.hard_pass),
                            "min_hard_margin": (
                                float(worst_h.min_margin) if worst_h is not None else None
                            ),
                            "total_penalty": float(best_local.score_report.constraint_penalty),
                            "objective_cost": float(best_local.score_report.objective_cost),
                        }
                    )

                if (
                    self.cfg.stop_if_feasible_for > 0
                    and feasible_streak >= self.cfg.stop_if_feasible_for
                ):
                    break

            best_local.history = history if self.cfg.keep_history else None

            if best_global is None or best_local.score < best_global.score:
                best_global = best_local

        if best_global is None:
            raise RuntimeError("Planner failed to produce any solution.")
        return best_global

    # -------------------------
    # Evaluation
    # -------------------------

    def _evaluate(
        self, problem: Problem, a: DecisionAssignment, rng: np.random.Generator
    ) -> PlanResult:
        """
        Evaluate a candidate decision assignment.

        If robustness is configured:
        - evaluate candidate across N uncertainty draws (seeds)
        - aggregate robust score (MEAN/WORST/CVaR)
        - still return nominal sim/plan for plotting + debug
        """
        # Nominal
        plan = problem.build_plan(a)
        sim = problem.simulate(plan, rng)
        crep = evaluate_constraints(sim, problem.constraints)

        # Score (nominal)
        score_cfg = self._score_config_for_problem(problem, robust=False)
        srep = score_plan(sim, problem.objective, crep, config=score_cfg)
        score_nominal = float(srep.total_score)

        # Big push away from hard-infeasible solutions (helps search converge faster)
        if not crep.hard_pass:
            score_nominal += float(self.cfg.hard_infeasible_penalty)

        robustness_summary: Optional[Dict[str, Any]] = None
        final_score = score_nominal
        final_score_report = srep

        if self._robustness_enabled(problem):
            robust = self._evaluate_robustness(problem, a)
            robustness_summary = robust["summary"]
            final_score = float(robust["robust_score"])
            # keep nominal report (still useful), but include robust score in metadata
            final_score_report = ScoreReport(
                objective=srep.objective,
                objective_cost=srep.objective_cost,
                constraint_penalty=srep.constraint_penalty,
                constraint_margin_reward=srep.constraint_margin_reward,
                total_score=float(final_score),
                constraint_summary=srep.constraint_summary,
                metadata={**dict(srep.metadata), "robust_aggregated_score": float(final_score)},
            )

        return PlanResult(
            assignment=a,
            plan=plan,
            sim_result=sim,
            constraints=crep,
            score_report=final_score_report,
            score=float(final_score),
            robustness=robustness_summary,
            history=None,
        )

    def _robustness_enabled(self, problem: Problem) -> bool:
        return bool(
            problem.robustness_cases > 0
            or (problem.robustness_seeds is not None and len(problem.robustness_seeds) > 0)
        )

    def _score_config_for_problem(self, problem: Problem, robust: bool) -> ScoreConfig:
        """
        Start from planner-level ScoreConfig, then override robust settings from Problem.
        """
        cfg = self.cfg.scoring
        if robust:
            return ScoreConfig(
                penalty_weight=cfg.penalty_weight,
                include_hard=cfg.include_hard,
                include_soft=cfg.include_soft,
                margin_reward_weight=cfg.margin_reward_weight,
                robust_aggregation=problem.robust_aggregation,
                cvar_alpha=problem.cvar_alpha,
            )
        return cfg

    def _evaluate_robustness(self, problem: Problem, a: DecisionAssignment) -> Dict[str, Any]:
        seeds: List[int]
        if problem.robustness_seeds is not None and len(problem.robustness_seeds) > 0:
            seeds = list(problem.robustness_seeds)
        else:
            base = int(self.cfg.seed)
            seeds = [base + i * 10007 for i in range(int(problem.robustness_cases))]

        sims: List[Any] = []
        creps: List[ConstraintReport] = []

        hard_pass: List[bool] = []
        worst_hard_margins: List[float] = []

        # Evaluate each case
        for s in seeds:
            rng = np.random.default_rng(int(s))
            plan = problem.build_plan(a)
            sim = problem.simulate(plan, rng)
            crep = evaluate_constraints(sim, problem.constraints)

            sims.append(sim)
            creps.append(crep)

            hard_pass.append(bool(crep.hard_pass))
            w = crep.worst(Severity.HARD)
            worst_hard_margins.append(float(w.min_margin) if w is not None else float("inf"))

        # Robust scoring aggregation (objective+penalty inside)
        robust_cfg = self._score_config_for_problem(problem, robust=True)
        rrep: RobustScoreReport = score_robust(
            sims=sims,
            objective=problem.objective,
            constraint_reports=creps,
            config=robust_cfg,
            keep_reports=False,
        )

        # Add hard infeasible penalty on a per-run basis conceptually via constraint penalty,
        # but we also expose feasibility rate explicitly for AeroHack reporting.
        pass_rate = float(np.mean(np.array(hard_pass, dtype=float))) if hard_pass else 0.0
        worst_margin_min = (
            float(np.min(np.array(worst_hard_margins, dtype=float)))
            if worst_hard_margins
            else float("inf")
        )

        # Helpful stats for validation bundle
        scores_np = np.asarray(rrep.per_run_scores, dtype=float)

        def _pct(x: np.ndarray, p: float) -> float:
            return float(np.percentile(x, p)) if x.size else float("inf")

        summary = {
            "cases": len(seeds),
            "hard_pass_rate": pass_rate,
            "worst_hard_margin_min": worst_margin_min,
            "robust_aggregation": str(problem.robust_aggregation.value),
            "cvar_alpha": (
                float(problem.cvar_alpha)
                if problem.robust_aggregation == RobustAggregation.CVAR
                else None
            ),
            "robust_score": float(rrep.aggregated_score),
            "mean_score": float(np.mean(scores_np)) if scores_np.size else float("inf"),
            "p50_score": _pct(scores_np, 50),
            "p90_score": _pct(scores_np, 90),
        }

        return {"robust_score": float(rrep.aggregated_score), "summary": summary}

    # -------------------------
    # Acceptance + annealing
    # -------------------------

    def _accept(self, cand_score: float, best_score: float, rng: np.random.Generator) -> bool:
        if cand_score < best_score:
            return True
        if self.cfg.accept_worse_prob <= 0.0:
            return False
        if rng.random() > self.cfg.accept_worse_prob:
            return False
        delta = cand_score - best_score
        T = max(1e-9, float(self.cfg.accept_worse_temp))
        p = float(np.exp(-delta / T))
        return rng.random() < p

    @staticmethod
    def _anneal(it: int, iters: int, start: float, end: float) -> float:
        if iters <= 1:
            return float(end)
        alpha = it / (iters - 1)
        return float((1 - alpha) * start + alpha * end)
