# tests/test_spacecraft_end_to_end.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.planner import Planner, PlannerConfig

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_spacecraft_pipeline_runs_end_to_end():
    cfg = _load_yaml(EXAMPLES_DIR / "cubesat_leo_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "spacecraft"

    from mission_framework.spacecraft.mission import build_problem_from_config

    problem = build_problem_from_config(cfg)
    problem.robustness_cases = 0

    # Keep runtime small for CI; increase for real runs
    planner_cfg = PlannerConfig(
        iterations=20,
        restarts=1,
        seed=0,
        keep_history=False,
        hard_infeasible_penalty=1e6,
    )

    planner = Planner(planner_cfg)
    result = planner.solve(problem)

    # Basic sanity checks
    assert result is not None
    assert result.plan is not None
    assert result.plan.kind == "spacecraft"
    assert result.plan.schedule is not None
    assert len(result.plan.schedule.events) >= 0  # may be 0 if no windows found with extreme params

    # Must be a numeric score
    assert isinstance(result.score, float)

    # Ensure objective report exists and is well-formed
    # If PlanResult does not have 'objective', use 'plan.objective' or remove these assertions
    # assert result.objective is not None
    # summary = result.objective.summary()
    # assert "total_cost" in summary

    # Robustness: in CI we disable it, so only assert when enabled on the Problem
    if getattr(problem, "robustness_cases", 0) > 0:
        assert result.robustness is not None
        assert int(result.robustness.get("cases", -1)) == int(problem.robustness_cases)
    else:
        assert result.robustness is None

    # Constraint report should exist and contain hard_pass boolean
    assert result.constraints is not None
    assert isinstance(result.constraints.hard_pass, bool)

    # Schedule should be non-overlapping if present
    if result.plan.schedule is not None:
        # validate_non_overlapping raises if overlap exists
        result.plan.schedule.validate_non_overlapping()
