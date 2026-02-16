# mission_framework/cli.py
"""
CLI entry point for running an aircraft or spacecraft scenario YAML.

Usage:
    python -m mission_framework.cli examples/aircraft_uav_demo.yaml
    python -m mission_framework.cli examples/cubesat_leo_demo.yaml

What this CLI does:
- Loads YAML scenario
- Builds a Problem (domain-specific builder, unified core interfaces)
- Runs the unified Planner
- Runs nominal simulation + optional robustness evaluation
- Prints summary + writes optional outputs (stubs / simple JSON)

NOTE:
This file assumes you'll implement:
- mission_framework.aircraft.mission.build_problem_from_config
- mission_framework.spacecraft.mission.build_problem_from_config
- mission_framework.reporting.* exporters (optional; can be simple prints at first)

Hackathon strategy:
- Make this runnable ASAP
- Then fill in domain modules incrementally
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml  # PyYAML

from mission_framework.core.planner import Planner, PlannerConfig, Problem
from mission_framework.core.constraints import Severity
from mission_framework.simulation.feasibility import format_feasibility_report


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _planner_config_from_yaml(cfg: Dict[str, Any]) -> PlannerConfig:
    p = cfg.get("planner", {}) or {}
    mut = p.get("mutation", {}) or {}

    return PlannerConfig(
        iterations=int(p.get("iterations", 2000)),
        restarts=int(p.get("restarts", 5)),
        penalty_weight=float(p.get("penalty_weight", 1000.0)),
        hard_infeasible_penalty=float(p.get("hard_infeasible_penalty", 1e6)),
        seed=int(p.get("seed", 0)),
        keep_history=bool(cfg.get("output", {}).get("save_history", True)),
        mutation=PlannerConfig().mutation.__class__(  # MutationConfig
            cont_sigma=float(mut.get("cont_sigma", 0.10)),
            cont_sigma_is_frac=bool(mut.get("cont_sigma_is_frac", True)),
            int_step=int(mut.get("int_step", 1)),
            p_flip=float(mut.get("p_flip", 0.05)),
            p_perm_swap=float(mut.get("p_perm_swap", 0.50)),
            perm_swaps=int(mut.get("perm_swaps", 2)),
        ),
    )


def _build_problem(cfg: Dict[str, Any]) -> Problem:
    scenario = cfg.get("scenario", {}) or {}
    stype = (scenario.get("type") or "").strip().lower()

    if stype == "aircraft":
        from mission_framework.aircraft.mission import build_problem_from_config
        return build_problem_from_config(cfg)

    if stype == "spacecraft":
        from mission_framework.spacecraft.mission import build_problem_from_config
        return build_problem_from_config(cfg)

    raise ValueError(f"Unknown scenario.type '{stype}'. Expected 'aircraft' or 'spacecraft'.")


def _write_json(out_path: Path, obj: Any) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run ORBITAL unified mission planning scenarios.")
    ap.add_argument("scenario_yaml", type=str, help="Path to scenario YAML (aircraft or spacecraft).")
    ap.add_argument("--outdir", type=str, default="runs", help="Output directory for reports/artifacts.")
    args = ap.parse_args()

    scenario_path = Path(args.scenario_yaml).resolve()
    cfg = _load_yaml(scenario_path)

    # Build problem
    problem = _build_problem(cfg)

    # Attach robustness settings (planner uses Problem.robustness_cases/seeds)
    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    # Planner
    planner_cfg = _planner_config_from_yaml(cfg)
    planner = Planner(planner_cfg)

    # Solve
    result = planner.solve(problem)

    # Console summary
    print("\n=== ORBITAL: Planning Complete ===")
    print(f"Scenario: {cfg.get('scenario', {}).get('name', '(unnamed)')}")
    print(f"Type:     {cfg.get('scenario', {}).get('type', '(unknown)')}")
    print(f"Score:    {result.score:.6g}")
    print(f"Feasible: {result.constraints.hard_pass}")

    worst_hard = result.constraints.worst(Severity.HARD)
    if worst_hard is not None:
        print(f"Worst HARD margin: {worst_hard.min_margin:+.6g} ({worst_hard.name})")

    print("\n--- Constraint Report (top worst first) ---")
    print(format_feasibility_report(result.constraints, max_lines=40))

    print("\n--- Objective Breakdown ---")
    print(json.dumps(result.objective.summary(), indent=2))

    if result.robustness is not None:
        print("\n--- Robustness Summary ---")
        print(json.dumps(result.robustness, indent=2))

    # Write basic artifacts (domain exporters can override later)
    outdir = Path(args.outdir).resolve() / scenario_path.stem
    outdir.mkdir(parents=True, exist_ok=True)

    _write_json(outdir / "objective.json", result.objective.summary())
    _write_json(outdir / "constraints.json", result.constraints.summary())
    if result.robustness is not None:
        _write_json(outdir / "robustness.json", result.robustness)

    # Plan export (minimal generic export)
    plan_payload = {
        "kind": getattr(result.plan, "kind", None),
        "metadata": getattr(result.plan, "metadata", {}),
        "waypoints": getattr(result.plan, "waypoints", None),
        "schedule": None,
    }
    # If schedule exists, serialize events
    sched = getattr(result.plan, "schedule", None)
    if sched is not None:
        plan_payload["schedule"] = [
            {
                "t_start": e.t_start,
                "t_end": e.t_end,
                "etype": str(e.etype),
                "label": e.label,
                "target_id": e.target_id,
                "location": e.location,
                "data": e.data,
            }
            for e in sched.events
        ]

    _write_json(outdir / "plan.json", plan_payload)

    # History
    if result.history is not None:
        _write_json(outdir / "history.json", result.history)

    print(f"\nWrote outputs to: {outdir}")


if __name__ == "__main__":
    main()
