# tests/test_spacecraft_end_to_end.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.planner import Planner, PlannerConfig
from mission_framework.core.types import EventType

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

    assert result is not None
    assert result.plan is not None
    assert result.plan.kind == "spacecraft"
    assert result.plan.schedule is not None
    assert len(result.plan.schedule.events) > 0

    assert isinstance(result.score, float)
    assert result.constraints.hard_pass is True

    scalars = result.sim_result.scalars
    assert scalars["obs_delivered"] >= 2.0
    assert scalars["mission_value"] >= 20.0
    assert scalars["cooldown_violation_s"] == 0.0
    assert scalars["min_battery_Wh"] >= 0.0

    summary = result.score_report.objective.summary()
    assert summary["total_cost"] == -scalars["mission_value"]

    event_types = [event.etype for event in result.plan.schedule.events]
    assert EventType.OBSERVATION in event_types
    assert EventType.DOWNLINK in event_types

    observed_targets = {
        event.target_id
        for event in result.plan.schedule.events
        if event.etype == EventType.OBSERVATION
    }
    assert observed_targets <= {"TGT1", "TGT2", "TGT3"}
    assert len(observed_targets) == int(scalars["obs_delivered"])

    # Robustness: in CI we disable it, so only assert when enabled on the Problem
    if getattr(problem, "robustness_cases", 0) > 0:
        assert result.robustness is not None
        assert int(result.robustness.get("cases", -1)) == int(problem.robustness_cases)
    else:
        assert result.robustness is None

    assert result.constraints is not None
    assert set(result.constraints.by_name()) >= {
        "battery_nonnegative",
        "cooldown_between_observations",
        "max_ops_per_orbit",
        "slew_feasible",
    }

    # Schedule should be non-overlapping if present
    if result.plan.schedule is not None:
        # validate_non_overlapping raises if overlap exists
        result.plan.schedule.validate_non_overlapping()
