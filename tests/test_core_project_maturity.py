from __future__ import annotations

import json

import numpy as np
import pytest

from mission_framework import (
    Bounds,
    ContinuousVar,
    DecisionAssignment,
    DecisionSpace,
    FunctionalObjectiveTerm,
    IntegerVar,
    Objective,
    Planner,
    PlannerConfig,
    Problem,
)
from mission_framework.core.planner import Problem as PlannerProblem


class SequenceDecisionSpace(DecisionSpace):
    """Deterministic space that offers one worse candidate after the initial best."""

    def __init__(self) -> None:
        super().__init__([IntegerVar("x", bounds=Bounds(0, 10))])

    def random_feasible(self, seed=None) -> DecisionAssignment:
        return DecisionAssignment({"x": np.array([0])})

    def mutate(self, a, rng, cfg, intensity) -> DecisionAssignment:
        return DecisionAssignment({"x": np.array([10])})


def test_problem_is_canonical_but_reexported_from_planner() -> None:
    assert PlannerProblem is Problem


def test_planner_preserves_best_result_when_accepting_worse_current_move() -> None:
    problem = Problem(
        decision_space=SequenceDecisionSpace(),
        build_plan=lambda decisions: decisions,
        simulate=lambda plan, rng=None: {"x": int(plan["x"][0])},
        constraints=[],
        objective=Objective([FunctionalObjectiveTerm("x", fn=lambda sim: sim["x"])]),
    )

    result = Planner(
        PlannerConfig(
            iterations=1,
            restarts=1,
            accept_worse_prob=1.0,
            accept_worse_temp=1e9,
            keep_history=False,
            seed=0,
        )
    ).solve(problem)

    assert result.score == pytest.approx(0.0)
    assert int(result.decisions["x"][0]) == 0


def test_plan_result_serializes_to_json_friendly_dict() -> None:
    problem = Problem(
        decision_space=SequenceDecisionSpace(),
        build_plan=lambda decisions: decisions,
        simulate=lambda plan, rng=None: {"x": int(plan["x"][0])},
        constraints=[],
        objective=Objective([FunctionalObjectiveTerm("x", fn=lambda sim: sim["x"])]),
    )

    result = Planner(PlannerConfig(iterations=0, restarts=1, keep_history=False)).solve(problem)

    payload = result.to_dict()
    assert payload["score"] == pytest.approx(0.0)
    assert payload["score_report"]["objective_cost"] == pytest.approx(0.0)
    json.dumps(payload)


def test_decision_space_rejects_duplicate_names_and_accepts_int_shape() -> None:
    var = ContinuousVar("throttle", shape=3, bounds=Bounds(0.0, 1.0))
    assert var.shape == (3,)

    with pytest.raises(ValueError, match="unique"):
        DecisionSpace(
            [
                ContinuousVar("x", bounds=Bounds(0.0, 1.0)),
                IntegerVar("x", bounds=Bounds(0, 2)),
            ]
        )
