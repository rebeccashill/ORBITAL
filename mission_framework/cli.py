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
- Prints summary + writes simple JSON artifacts

Assumes you'll implement:
- mission_framework.aircraft.mission.build_problem_from_config
- mission_framework.spacecraft.mission.build_problem_from_config
- mission_framework.reporting.* exporters (optional; can be simple prints first)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml  # PyYAML

from mission_framework.core.constraints import Severity
from mission_framework.core.decision_variables import MutationConfig
from mission_framework.core.objective import RobustAggregation, ScoreConfig
from mission_framework.core.planner import Planner, PlannerConfig, Problem
from mission_framework.scenario_validation import ScenarioValidationError, validate_scenario_config
from mission_framework.simulation.feasibility import format_feasibility_report


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _planner_config_from_yaml(cfg: Dict[str, Any]) -> PlannerConfig:
    p = cfg.get("planner", {}) or {}
    mut = p.get("mutation", {}) or {}

    # Scoring config (unified with core/objective.py)
    scoring = ScoreConfig(
        penalty_weight=float(p.get("penalty_weight", 1000.0)),
        include_hard=True,
        include_soft=True,
        margin_reward_weight=float(p.get("margin_reward_weight", 0.0)),
        robust_aggregation=RobustAggregation.MEAN,  # overridden in Problem when robustness is enabled
        cvar_alpha=float(p.get("cvar_alpha", 0.8)),
    )

    return PlannerConfig(
        iterations=int(p.get("iterations", 2000)),
        restarts=int(p.get("restarts", 5)),
        scoring=scoring,
        hard_infeasible_penalty=float(p.get("hard_infeasible_penalty", 1e6)),
        seed=int(p.get("seed", 0)),
        keep_history=bool(cfg.get("output", {}).get("save_history", True)),
        history_stride=int(p.get("history_stride", 1)),
        mutation=MutationConfig(
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
    ap.add_argument(
        "scenario_yaml", type=str, help="Path to scenario YAML (aircraft or spacecraft)."
    )
    ap.add_argument(
        "--outdir", type=str, default="runs", help="Output directory for reports/artifacts."
    )
    ap.add_argument("--iterations", type=int, default=None, help="Override planner.iterations")
    ap.add_argument("--restarts", type=int, default=None, help="Override planner.restarts")
    ap.add_argument("--robustness", type=int, default=None, help="Override robustness.cases")
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducible runs")
    ap.add_argument("--no-plots", action="store_true", help="Skip PNG plot generation")

    args = ap.parse_args()
    if args.seed is not None:
        import random

        random.seed(args.seed)
        try:
            import numpy as np

            np.random.seed(args.seed)
        except Exception:
            pass

    scenario_path = Path(args.scenario_yaml).resolve()
    cfg = _load_yaml(scenario_path)

    # Optional overrides for fast runs
    if args.iterations is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["iterations"] = int(args.iterations)

    if args.restarts is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["restarts"] = int(args.restarts)

    if args.robustness is not None:
        cfg.setdefault("robustness", {})
        cfg["robustness"]["cases"] = int(args.robustness)

    if args.seed is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["seed"] = int(args.seed)

    try:
        validate_scenario_config(cfg)
    except ScenarioValidationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    generate_plots = not bool(args.no_plots)

    # Build problem
    problem = _build_problem(cfg)

    # Attach robustness settings (planner uses Problem.robustness_cases/seeds)
    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    # Optional robust aggregation settings from YAML (nice for AeroHack tuning)
    # Example:
    # robustness:
    #   cases: 50
    #   aggregation: cvar
    #   cvar_alpha: 0.8
    agg = (rob.get("aggregation") or "").strip().lower()
    if agg in ("mean", "worst", "cvar"):
        problem.robust_aggregation = RobustAggregation(agg)
    if "cvar_alpha" in rob:
        problem.cvar_alpha = float(rob["cvar_alpha"])

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

    print("\n--- Score Breakdown ---")
    print(json.dumps(result.score_report.to_jsonable(), indent=2))

    if result.robustness is not None:
        print("\n--- Robustness Summary ---")
        print(json.dumps(result.robustness, indent=2))

    # Write basic artifacts
    outdir = Path(args.outdir).resolve() / scenario_path.stem
    outdir.mkdir(parents=True, exist_ok=True)

    scenario_type = str(cfg.get("scenario", {}).get("type", "")).strip().lower()

    if scenario_type == "aircraft":
        # Optional human-readable output
        try:
            from mission_framework.reporting.flight_output import (
                export_waypoints_csv,
                print_flight_plan,
            )

            print("\n--- Flight Plan ---")
            print(print_flight_plan(result.plan))
            export_waypoints_csv(result.plan, outdir / "waypoints.csv")
        except Exception as e:
            print(f"(flight reporting skipped: {e})")

        if generate_plots:
            try:
                from mission_framework.visualization.aircraft_plots import plot_aircraft_mission

                mission_name = cfg.get("scenario", {}).get("name", "Aircraft Mission")
                plot_files = plot_aircraft_mission(
                    result.plan, result.sim_result, outdir, mission_name
                )
                if plot_files:
                    print("\n--- Plots Generated ---")
                    for plot_name, plot_path in plot_files.items():
                        print(f"  {plot_name}: {plot_path.name}")
            except Exception as e:
                print(f"(plot generation skipped: {e})")

    elif scenario_type == "spacecraft":
        try:
            from mission_framework.reporting.schedule_output import (
                export_schedule_csv,
                print_schedule,
            )

            print("\n--- 7-Day Schedule ---")
            print(print_schedule(result.plan))
            export_schedule_csv(result.plan, outdir / "schedule.csv")
        except Exception as e:
            print(f"(schedule reporting skipped: {e})")

        if generate_plots:
            try:
                from mission_framework.visualization.spacecraft_plots import plot_spacecraft_mission

                mission_name = cfg.get("scenario", {}).get("name", "Spacecraft Mission")
                plot_files = plot_spacecraft_mission(
                    result.plan, result.sim_result, outdir, mission_name
                )
                if plot_files:
                    print("\n--- Plots Generated ---")
                    for plot_name, plot_path in plot_files.items():
                        print(f"  {plot_name}: {plot_path.name}")
            except Exception as e:
                print(f"(plot generation skipped: {e})")

    # Core JSON artifacts (judge-friendly)
    _write_json(outdir / "score.json", result.score_report.to_jsonable())
    _write_json(
        outdir / "constraints.json",
        (
            result.constraints.to_jsonable()
            if hasattr(result.constraints, "to_jsonable")
            else result.constraints.summary()
        ),
    )
    if result.robustness is not None:
        _write_json(outdir / "robustness.json", result.robustness)

    # Minimal generic plan export
    plan_payload: Dict[str, Any] = {
        "kind": getattr(result.plan, "kind", None),
        "metadata": getattr(result.plan, "metadata", {}),
        "waypoints": getattr(result.plan, "waypoints", None),
        "schedule": None,
    }
    sched = getattr(result.plan, "schedule", None)
    if sched is not None:
        plan_payload["schedule"] = [
            {
                "t_start": getattr(e, "t_start", None),
                "t_end": getattr(e, "t_end", None),
                "etype": str(getattr(e, "etype", None)),
                "label": getattr(e, "label", None),
                "target_id": getattr(e, "target_id", None),
                "location": getattr(e, "location", None),
                "data": getattr(e, "data", None),
            }
            for e in getattr(sched, "events", [])
        ]

    _write_json(outdir / "plan.json", plan_payload)

    # History (if enabled)
    if result.history is not None:
        _write_json(outdir / "history.json", result.history)

    print(f"\nWrote outputs to: {outdir}")


if __name__ == "__main__":
    main()
