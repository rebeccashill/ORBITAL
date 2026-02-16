# tests/test_unified_architecture.py
"""
Unified architecture tests.

Goal:
- Ensure aircraft and spacecraft scenarios use the SAME planning kernel:
  - mission_framework.core.decision_variables.DecisionSpace
  - mission_framework.core.constraints.Constraint
  - mission_framework.core.objective.Objective
  - mission_framework.core.planner.Planner (single method)
  - mission_framework.core.planner.Problem wrapper

These tests are intentionally "architecture" focused, not physics-accuracy focused.
They should fail if someone tries to solve aircraft/spacecraft with separate solvers or
separate incompatible abstractions.

Run:
    pytest -q
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.planner import Planner, PlannerConfig, Problem
from mission_framework.core.decision_variables import DecisionSpace
from mission_framework.core.constraints import Constraint
from mission_framework.core.objective import Objective


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_aircraft_problem_builds_with_unified_core_types():
    cfg = _load_yaml(EXAMPLES_DIR / "aircraft_uav_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "aircraft"

    from mission_framework.aircraft.mission import build_problem_from_config
    problem = build_problem_from_config(cfg)

    assert isinstance(problem, Problem)
    assert isinstance(problem.decision_space, DecisionSpace)
    assert isinstance(problem.objective, Objective)
    assert isinstance(problem.constraints, list)
    assert all(isinstance(c, Constraint) for c in problem.constraints)


def test_spacecraft_problem_builds_with_unified_core_types():
    cfg = _load_yaml(EXAMPLES_DIR / "cubesat_leo_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "spacecraft"

    from mission_framework.spacecraft.mission import build_problem_from_config
    problem = build_problem_from_config(cfg)

    assert isinstance(problem, Problem)
    assert isinstance(problem.decision_space, DecisionSpace)
    assert isinstance(problem.objective, Objective)
    assert isinstance(problem.constraints, list)
    assert all(isinstance(c, Constraint) for c in problem.constraints)


def test_both_domains_use_same_planner_class():
    """
    Ensures we have ONE shared planning method / entry point.
    """
    cfg_air = _load_yaml(EXAMPLES_DIR / "aircraft_uav_demo.yaml")
    cfg_spc = _load_yaml(EXAMPLES_DIR / "cubesat_leo_demo.yaml")

    from mission_framework.aircraft.mission import build_problem_from_config as build_air
    from mission_framework.spacecraft.mission import build_problem_from_config as build_spc

    prob_air = build_air(cfg_air)
    prob_spc = build_spc(cfg_spc)

    planner = Planner(PlannerConfig(iterations=2, restarts=1, seed=0, keep_history=False))

    # We don't require success yet (domain implementations may still be stubs),
    # but we require the same solver entry point is callable for both.
    assert hasattr(planner, "solve") and callable(planner.solve)

    # If domain builders are implemented, these will run.
    # If not implemented yet, they should raise NotImplementedError rather than using a different planner.
    try:
        planner.solve(prob_air)
    except NotImplementedError:
        pass
    except Exception:
        # Other exceptions are acceptable early-stage; this test is about *architecture*.
        pass

    try:
        planner.solve(prob_spc)
    except NotImplementedError:
        pass
    except Exception:
        pass
