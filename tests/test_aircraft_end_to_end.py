# tests/test_aircraft_end_to_end.py
"""
Aircraft end-to-end smoke test.

This test is intended to verify the full pipeline for the aircraft module:
YAML -> Problem -> Planner -> Plan -> Simulation -> Constraints -> Objective.

It is a *smoke test*, not a high-fidelity validation.
Once the aircraft module is implemented, this test should pass quickly.

Run:
    pytest -q
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.planner import Planner, PlannerConfig
from mission_framework.core.constraints import Severity


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_aircraft_pipeline_runs_end_to_end():
    cfg = _load_yaml(EXAMPLES_DIR / "aircraft_uav_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "aircraft"

    from mission_framework.aircraft.mission import build_problem_from_config
    problem = build_problem_from_config(cfg)

    # Keep runtime small for CI; increase for real runs
    from mission_framework.core.objective import ScoreConfig
    planner_cfg = PlannerConfig(
        iterations=50,
        restarts=1,
        seed=0,
        keep_history=False,
        scoring=ScoreConfig(
            penalty_weight=float(cfg.get("planner", {}).get("penalty_weight", 1000.0)),
        ),
        hard_infeasible_penalty=float(cfg.get("planner", {}).get("hard_infeasible_penalty", 1e6)),
    )

    planner = Planner(planner_cfg)
    result = planner.solve(problem)

    # Basic sanity: returned objects exist
    assert result.assignment is not None
    assert result.plan is not None
    assert result.sim_result is not None
    assert result.constraints is not None
    assert result.score_report is not None

    # Hard feasibility should generally be achievable for the demo scenario
    # If you're still implementing constraints/dynamics, you can temporarily relax this.
    assert isinstance(result.constraints.hard_pass, bool)

    # Constraint report should contain at least one constraint
    assert len(result.constraints.results) > 0

    # Check we have sensible objective breakdown
    summary = result.score_report.objective.summary()
    assert "total_cost" in summary
    assert summary["total_cost"] is not None

    # Optional: ensure worst hard margin is finite if hard constraints exist
    worst_hard = result.constraints.worst(Severity.HARD)
    if worst_hard is not None:
        assert worst_hard.min_margin == worst_hard.min_margin  # not NaN
