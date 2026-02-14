# mission_framework/core/planner.py
"""
Single unified planning method: Simulation-in-the-loop stochastic optimization.

Why this planner:
- Works for BOTH aircraft (route/timing/control) and spacecraft (7-day scheduling).
- Handles mixed decision variables (continuous/integer/binary/permutation) without MILP pain.
- Naturally supports robustness: evaluate candidates across multiple uncertainty cases.

Approach:
- Maintain a current best solution (DecisionAssignment).
- Iterate:
    - mutate current best to create a candidate
    - decode/build a plan (domain-specific, provided by Problem)
    - simulate plan (domain-specific, provided by Problem)
    - evaluate constraints (domain-agnostic)
    - evaluate objective (domain-agnostic)
    - score = objective_cost + penalty_weight * constraint_penalty
    - accept if score improves (or via simulated annealing option)

This is "one planning method" across both domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from mission_framework.core.decision_variables import DecisionAssignment, DecisionSpace, MutationConfig
from mission_framework.core.constraints import Constraint, ConstraintReport, evaluate_constraints, Severity
from mission_framework.core.objective import Objective, ObjectiveReport


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
    build_plan: Callable[[DecisionAssignment], Any]                # decisions -> plan object
    simulate: Callable[[Any, Optional[np.random.Generator]], Any]  # (plan, rng) -> sim_result
    constraints: List[Constraint]
    objective: Objective

    # Optional: robustness evaluation
    robustness_cases: int = 0  # if >0, evaluate each candidate across N random seeds
    # Optional: provide an explicit set of seeds (overrides robustness_cases)
    robustness_seeds: Optional[List[int]] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    """
    What the planner returns.
    Keep it simple and report-heavy (hackathon friendly).
    """
    assignment: DecisionAssignment
    plan: Any
    sim_result: Any
    constraints: ConstraintReport
    objective: ObjectiveReport
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

    # Scoring
    penalty_weight: float = 1000.0  # multiplier for constraint penalties
    hard_infeasible_penalty: float = 1e6  # extra penalty if any hard constraint fails

    # Acceptance policy
    accept_worse_prob: float = 0.0  # set >0 to allow occasional worse moves (SA-like)
    accept_worse_temp: float = 1.0  # temperature for worse-move acceptance

    # Early stopping
    stop_if_feasible_for: int = 0  # if >0, stop after N consecutive feasible improvements

    # Reproducibility
    seed: int = 0

    # Logging
    keep_history: bool = True
    history_stride: int = 1  # store every k iterations


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
            # Derive a restart-specific RNG
            seed_r = int(rng_master.integers(0, 2**31 - 1))
            rng = np.random.default_rng(seed_r)

            # Initial candidate
            current = problem.decision_space.random_feasible(seed=int(rng.integers(0, 2**31 - 1)))
            current_eval = self._evaluate(problem, current, rng)
            best_local = current_eval

            history: List[Dict[str, Any]] = []
            feasible_streak = 0

            for it in range(self.cfg.iterations):
                intensity = self._anneal(it, self.cfg.iterations, self.cfg.intensity_start, self.cfg.intensity_end)
                cand = problem.decision_space.mutate(best_local.assignment, rng=rng, cfg=self.cfg.mutation, intensity=intensity)

                cand_eval = self._evaluate(problem, cand, rng)

                accept = self._accept(cand_eval.score, best_local.score, rng)
                if accept:
                    best_local = cand_eval

                # Feasible improvement tracking (optional early stop)
                if best_local.constraints.hard_pass:
                    feasible_streak += 1
                else:
                    feasible_streak = 0

                if self.cfg.keep_history and (it % max(1, self.cfg.history_stride) == 0):
                    history.append({
                        "restart": r,
                        "iter": it,
                        "best_score": float(best_local.score),
                        "hard_pass": bool(best_local.constraints.hard_pass),
                        "min_hard_margin": (
                            float(best_local.constraints.worst(Severity.HARD).min_margin)
                            if best_local.constraints.worst(Severity.HARD) is not None else None
                        ),
                        "total_penalty": float(best_local.constraints.total_penalty()),
                        "objective_cost": float(best_local.objective.total_cost()),
                    })

                if self.cfg.stop_if_feasible_for > 0 and feasible_streak >= self.cfg.stop_if_feasible_for:
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

    def _evaluate(self, problem: Problem, a: DecisionAssignment, rng: np.random.Generator) -> PlanResult:
        """
        Evaluate a candidate decision assignment.

        If robustness_cases/seeds are configured, we evaluate across multiple
        random seeds and aggregate:
        - feasibility rate (hard constraints)
        - worst-case margin
        - mean score, p90 score
        We still return the *nominal* sim/plan for reporting, but include robustness summary.
        """
        # Nominal evaluation
        plan = problem.build_plan(a)
        sim = problem.simulate(plan, rng)
        crep = evaluate_constraints(sim, problem.constraints)
        orep = problem.objective.evaluate(sim)

        score_nominal = self._score(problem, orep.total_cost(), crep)

        robustness_summary = None
        if problem.robustness_cases > 0 or (problem.robustness_seeds is not None and len(problem.robustness_seeds) > 0):
            robustness_summary = self._evaluate_robustness(problem, a)

            # You can choose to optimize the robust score (mean or p90) rather than nominal:
            # For hackathon wins, optimizing worst-case or p90 often looks strong.
            # We'll use p90 score by default if provided; otherwise mean.
            score = robustness_summary.get("p90_score", robustness_summary["mean_score"])
        else:
            score = score_nominal

        return PlanResult(
            assignment=a,
            plan=plan,
            sim_result=sim,
            constraints=crep,
            objective=orep,
            score=float(score),
            robustness=robustness_summary,
            history=None,
        )

    def _score(self, problem: Problem, objective_cost: float, crep: ConstraintReport) -> float:
        penalty = crep.total_penalty(include_hard=True, include_soft=True)
        score = float(objective_cost + self.cfg.penalty_weight * penalty)

        if not crep.hard_pass:
            score += float(self.cfg.hard_infeasible_penalty)

        return score

    def _evaluate_robustness(self, problem: Problem, a: DecisionAssignment) -> Dict[str, Any]:
        seeds: List[int]
        if problem.robustness_seeds is not None and len(problem.robustness_seeds) > 0:
            seeds = list(problem.robustness_seeds)
        else:
            # deterministic seeds based on planner seed + assignment hash-ish
            base = self.cfg.seed
            seeds = [base + i * 10007 for i in range(problem.robustness_cases)]

        scores: List[float] = []
        hard_pass: List[bool] = []
        worst_hard_margins: List[float] = []
        penalties: List[float] = []
        objective_costs: List[float] = []

        for s in seeds:
            rng = np.random.default_rng(int(s))
            plan = problem.build_plan(a)
            sim = problem.simulate(plan, rng)
            crep = evaluate_constraints(sim, problem.constraints)
            orep = problem.objective.evaluate(sim)

            objective_cost = float(orep.total_cost())
            score = self._score(problem, objective_cost, crep)

            scores.append(float(score))
            hard_pass.append(bool(crep.hard_pass))
            penalties.append(float(crep.total_penalty()))
            objective_costs.append(objective_cost)

            w = crep.worst(Severity.HARD)
            worst_hard_margins.append(float(w.min_margin) if w is not None else float("inf"))

        scores_np = np.array(scores, dtype=float)
        pass_rate = float(np.mean(np.array(hard_pass, dtype=float)))

        def _pct(x: np.ndarray, p: float) -> float:
            return float(np.percentile(x, p))

        return {
            "cases": len(seeds),
            "hard_pass_rate": pass_rate,
            "worst_hard_margin_min": float(np.min(np.array(worst_hard_margins, dtype=float))),
            "mean_score": float(np.mean(scores_np)),
            "p50_score": _pct(scores_np, 50),
            "p90_score": _pct(scores_np, 90),
            "mean_objective_cost": float(np.mean(np.array(objective_costs, dtype=float))),
            "mean_penalty": float(np.mean(np.array(penalties, dtype=float))),
        }

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
        # SA-like: accept with probability exp(-(delta)/T)
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
