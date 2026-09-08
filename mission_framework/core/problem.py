# mission_framework/core/problem.py
"""
Problem container (domain-agnostic).

This file defines the *glue object* that connects the unified core pieces:

- DecisionSpace (what can be chosen)
- build_plan(decisions) -> plan (how choices become an executable plan/schedule)
- simulate(plan, rng) -> sim_result (how a plan is rolled forward in time)
- constraints (what must/may be satisfied)
- objective (what to optimize)

It is intentionally domain-agnostic so BOTH:
- aircraft route/timing/control problems
- spacecraft multi-day scheduling problems
fit the same interface.

Notes:
- Constraints and objective operate on `sim_result` (any python object).
- Robustness support: evaluate the same candidate across multiple random seeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from mission_framework.core.constraints import Constraint, ConstraintGroup
from mission_framework.core.decision_variables import DecisionAssignment, DecisionSpace
from mission_framework.core.objective import Objective, RobustAggregation


@dataclass
class Problem:
    """
    Domain-agnostic planning problem definition.

    The planner treats this as a black box:
      decisions -> plan -> simulation -> {constraints, objective} -> score
    """

    # What the optimizer can choose
    decision_space: DecisionSpace

    # Domain hook: convert decisions into an executable plan/schedule
    build_plan: Callable[[DecisionAssignment], Any]

    # Domain hook: run the plan forward (optionally using rng for uncertainty)
    simulate: Callable[[Any, Optional[np.random.Generator]], Any]

    # Domain-agnostic evaluators
    constraints: List[Union[Constraint, ConstraintGroup]]
    objective: Objective

    # Robustness / uncertainty evaluation
    robustness_cases: int = 0
    robustness_seeds: Optional[List[int]] = None
    robust_aggregation: RobustAggregation = RobustAggregation.CVAR
    cvar_alpha: float = 0.8

    # Optional metadata (scenario name, units, description, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_robustness_seeds(
        self,
        rng_master: np.random.Generator,
    ) -> List[int]:
        """
        Returns the list of seeds to use for robustness evaluation.

        Priority:
        1) If robustness_seeds is provided, use it.
        2) Else if robustness_cases > 0, generate that many seeds from rng_master.
        3) Else return [] (no robustness).
        """
        if self.robustness_seeds is not None:
            return list(self.robustness_seeds)

        if self.robustness_cases and self.robustness_cases > 0:
            # Use uint32 range for portability with numpy RNG seeding
            return [int(rng_master.integers(0, 2**32 - 1)) for _ in range(self.robustness_cases)]

        return []

    def validate(self) -> None:
        """
        Light validation to catch common wiring mistakes early.
        Raises ValueError with actionable messages.
        """
        if not isinstance(self.decision_space, DecisionSpace):
            raise ValueError("Problem.decision_space must be a DecisionSpace.")

        if not callable(self.build_plan):
            raise ValueError("Problem.build_plan must be callable(decisions) -> plan.")

        if not callable(self.simulate):
            raise ValueError("Problem.simulate must be callable(plan, rng) -> sim_result.")

        if self.constraints is None:
            raise ValueError("Problem.constraints must be a list (can be empty).")

        if not isinstance(self.constraints, list):
            raise ValueError("Problem.constraints must be a list of Constraint or ConstraintGroup objects.")

        for c in self.constraints:
            if not isinstance(c, (Constraint, ConstraintGroup)):
                raise ValueError(f"All constraints must be instances of Constraint. Got: {type(c)}")

        if not isinstance(self.objective, Objective):
            raise ValueError("Problem.objective must be an Objective instance.")

        if self.robustness_cases < 0:
            raise ValueError("Problem.robustness_cases cannot be negative.")

        if self.robustness_seeds is not None and len(self.robustness_seeds) == 0:
            raise ValueError("Problem.robustness_seeds was provided but is empty.")

        if not isinstance(self.robust_aggregation, RobustAggregation):
            raise ValueError("Problem.robust_aggregation must be a RobustAggregation value.")

        if not 0.0 < float(self.cvar_alpha) < 1.0:
            raise ValueError("Problem.cvar_alpha must be in (0, 1).")
