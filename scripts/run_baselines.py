#!/usr/bin/env python3
"""
Generate baseline comparison reports for ORBITAL.

The report compares the ORBITAL planner against simple, auditable baselines:
- random_search: sample N feasible assignments and keep the best nominal score
- greedy_routing: aircraft nearest-neighbor waypoint order
- earliest_deadline: spacecraft observe/downlink at earliest available windows

Outputs:
- outputs/validation/baselines/baselines.csv
- outputs/validation/baselines/baselines.md
- outputs/validation/baselines/README.txt
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import yaml

from mission_framework.cli import _build_problem, _planner_config_from_yaml
from mission_framework.core.constraints import Severity
from mission_framework.core.decision_variables import DecisionAssignment
from mission_framework.core.objective import RobustAggregation
from mission_framework.core.planner import Planner, PlannerConfig
from mission_framework.core.problem import Problem
from mission_framework.core.solutions import PlanResult

DEFAULT_AIRCRAFT_SCENARIO = "examples/aircraft_uav_demo.yaml"
DEFAULT_SPACECRAFT_SCENARIO = "examples/cubesat_leo_demo.yaml"
DEFAULT_OUTPUT_CSV = "outputs/validation/baselines/baselines.csv"

FIELDNAMES = [
    "domain",
    "scenario",
    "planner",
    "category",
    "samples",
    "iterations",
    "restarts",
    "seed",
    "score",
    "feasible",
    "objective_cost",
    "constraint_penalty",
    "worst_hard_constraint",
    "worst_hard_margin",
    "runtime_s",
    "robustness_cases",
    "robust_hard_pass_rate",
    "robust_worst_hard_margin",
    "robust_score",
]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Scenario YAML must contain a mapping at top level: {path}")
    return cfg


def scenario_type(cfg: Dict[str, Any]) -> str:
    scenario = cfg.get("scenario", {}) or {}
    return str(scenario.get("type", "")).strip().lower()


def scenario_name(cfg: Dict[str, Any]) -> str:
    scenario = cfg.get("scenario", {}) or {}
    return str(scenario.get("name", "(unnamed)"))


def with_overrides(
    cfg: Dict[str, Any],
    *,
    iterations: Optional[int] = None,
    restarts: Optional[int] = None,
    robustness_cases: Optional[int] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    out = deepcopy(cfg)

    if iterations is not None:
        out.setdefault("planner", {})
        out["planner"]["iterations"] = int(iterations)
    if restarts is not None:
        out.setdefault("planner", {})
        out["planner"]["restarts"] = int(restarts)
    if seed is not None:
        out.setdefault("planner", {})
        out["planner"]["seed"] = int(seed)
    if robustness_cases is not None:
        out.setdefault("robustness", {})
        out["robustness"]["cases"] = int(robustness_cases)

    return out


def build_problem(cfg: Dict[str, Any]) -> Problem:
    problem = _build_problem(cfg)

    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    aggregation = str(rob.get("aggregation", "")).strip().lower()
    if aggregation in {"mean", "worst", "cvar"}:
        problem.robust_aggregation = RobustAggregation(aggregation)
    if "cvar_alpha" in rob:
        problem.cvar_alpha = float(rob["cvar_alpha"])

    return problem


def planner_config(cfg: Dict[str, Any]) -> PlannerConfig:
    cfg_out = _planner_config_from_yaml(cfg)
    cfg_out.keep_history = False
    return cfg_out


def apply_robustness_settings(problem: Problem, cfg: Dict[str, Any]) -> None:
    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    aggregation = str(rob.get("aggregation", "")).strip().lower()
    if aggregation in {"mean", "worst", "cvar"}:
        problem.robust_aggregation = RobustAggregation(aggregation)
    if "cvar_alpha" in rob:
        problem.cvar_alpha = float(rob["cvar_alpha"])


def evaluate_assignment(
    problem: Problem,
    cfg: Dict[str, Any],
    assignment: DecisionAssignment,
    *,
    seed: int,
    robustness_cases: int,
) -> PlanResult:
    robust_cfg = with_overrides(cfg, robustness_cases=robustness_cases, seed=seed)
    pcfg = planner_config(robust_cfg)
    rng = np.random.default_rng(seed)

    old_cases = problem.robustness_cases
    old_aggregation = problem.robust_aggregation
    old_cvar_alpha = problem.cvar_alpha
    try:
        apply_robustness_settings(problem, robust_cfg)
        return Planner(pcfg)._evaluate(problem, assignment, rng)
    finally:
        problem.robustness_cases = old_cases
        problem.robust_aggregation = old_aggregation
        problem.cvar_alpha = old_cvar_alpha


def run_orbital(
    problem: Problem,
    cfg: Dict[str, Any],
    *,
    iterations: int,
    restarts: int,
    robustness_cases: int,
    seed: int,
) -> tuple[PlanResult, float]:
    nominal_cfg = with_overrides(
        cfg,
        iterations=iterations,
        restarts=restarts,
        robustness_cases=0,
        seed=seed,
    )
    pcfg = planner_config(nominal_cfg)

    t0 = time.perf_counter()
    nominal_result = Planner(pcfg).solve(problem)
    final_result = evaluate_assignment(
        problem,
        cfg,
        nominal_result.assignment,
        seed=seed,
        robustness_cases=robustness_cases,
    )
    runtime_s = time.perf_counter() - t0
    return final_result, runtime_s


def run_random_search(
    problem: Problem,
    cfg: Dict[str, Any],
    *,
    samples: int,
    robustness_cases: int,
    seed: int,
) -> tuple[PlanResult, float]:
    if samples < 1:
        raise ValueError("random_search requires at least one sample.")

    nominal_cfg = with_overrides(
        cfg,
        iterations=1,
        restarts=1,
        robustness_cases=0,
        seed=seed,
    )
    pcfg = planner_config(nominal_cfg)
    planner = Planner(pcfg)
    rng = np.random.default_rng(seed)

    best: Optional[PlanResult] = None

    t0 = time.perf_counter()
    for _ in range(samples):
        assignment = problem.decision_space.random_feasible(seed=int(rng.integers(0, 2**31 - 1)))
        result = planner._evaluate(problem, assignment, rng)
        if best is None or result.score < best.score:
            best = result

    if best is None:
        raise RuntimeError("random_search did not produce a candidate.")

    final_result = evaluate_assignment(
        problem,
        cfg,
        best.assignment,
        seed=seed,
        robustness_cases=robustness_cases,
    )
    runtime_s = time.perf_counter() - t0
    return final_result, runtime_s


def _distance_xy(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    dx = float(left.get("x_m", 0.0)) - float(right.get("x_m", 0.0))
    dy = float(left.get("y_m", 0.0)) - float(right.get("y_m", 0.0))
    return math.hypot(dx, dy)


def greedy_aircraft_assignment(cfg: Dict[str, Any]) -> DecisionAssignment:
    mission = cfg.get("mission", {}) or {}
    waypoints = [dict(w) for w in mission.get("waypoints", []) or []]
    if not waypoints:
        raise ValueError("greedy_routing requires aircraft mission.waypoints.")

    current = dict(cfg.get("initial_state", {}) or {})
    remaining = list(waypoints)
    order: list[str] = []

    while remaining:
        next_wp = min(remaining, key=lambda wp: (_distance_xy(current, wp), str(wp.get("id", ""))))
        remaining.remove(next_wp)
        order.append(str(next_wp.get("id", "")))
        current = next_wp

    vehicle = cfg.get("vehicle", {}) or {}
    min_speed = float(vehicle.get("min_speed_mps", 12.0))
    max_speed = float(vehicle.get("max_speed_mps", 30.0))
    cruise_speed = float(vehicle.get("cruise_speed_mps", (min_speed + max_speed) / 2.0))
    cruise_speed = float(np.clip(cruise_speed, min_speed, max_speed))

    return DecisionAssignment(
        {
            "visit_order": order,
            "cruise_speed_mps": np.array([cruise_speed], dtype=float),
        }
    )


def run_greedy_routing(
    problem: Problem,
    cfg: Dict[str, Any],
    *,
    robustness_cases: int,
    seed: int,
) -> tuple[PlanResult, float]:
    t0 = time.perf_counter()
    assignment = greedy_aircraft_assignment(cfg)
    final_result = evaluate_assignment(
        problem,
        cfg,
        assignment,
        seed=seed,
        robustness_cases=robustness_cases,
    )
    runtime_s = time.perf_counter() - t0
    return final_result, runtime_s


def _target_deadline_key(target: Dict[str, Any]) -> tuple[str, str]:
    windows = target.get("time_windows", []) or []
    deadlines = [str(w.get("end_utc", "")) for w in windows if w.get("end_utc")]
    deadline = min(deadlines) if deadlines else "9999-12-31T23:59:59Z"
    return deadline, str(target.get("id", ""))


def earliest_deadline_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    mission = out.setdefault("mission", {})
    mission["targets"] = sorted(
        [dict(t) for t in mission.get("targets", []) or []],
        key=_target_deadline_key,
    )
    return out


def earliest_deadline_assignment(cfg: Dict[str, Any]) -> DecisionAssignment:
    targets = (cfg.get("mission", {}) or {}).get("targets", []) or []
    if not targets:
        raise ValueError("earliest_deadline requires spacecraft mission.targets.")

    values: Dict[str, Any] = {}
    for target in sorted((dict(t) for t in targets), key=_target_deadline_key):
        target_id = str(target.get("id", ""))
        values[f"select_{target_id}"] = 1
        values[f"obs_offset_{target_id}"] = np.array([0.0], dtype=float)

    values["downlink_policy"] = 0
    return DecisionAssignment(values)


def run_earliest_deadline(
    problem: Problem,
    cfg: Dict[str, Any],
    *,
    robustness_cases: int,
    seed: int,
) -> tuple[PlanResult, float]:
    t0 = time.perf_counter()
    assignment = earliest_deadline_assignment(cfg)
    final_result = evaluate_assignment(
        problem,
        cfg,
        assignment,
        seed=seed,
        robustness_cases=robustness_cases,
    )
    runtime_s = time.perf_counter() - t0
    return final_result, runtime_s


def row_for_result(
    cfg: Dict[str, Any],
    *,
    planner_name: str,
    category: str,
    result: PlanResult,
    runtime_s: float,
    seed: int,
    samples: Optional[int],
    iterations: Optional[int],
    restarts: Optional[int],
    robustness_cases: int,
) -> Dict[str, Any]:
    worst = result.constraints.worst(Severity.HARD)
    robustness = result.robustness or {}

    return {
        "domain": scenario_type(cfg),
        "scenario": scenario_name(cfg),
        "planner": planner_name,
        "category": category,
        "samples": "" if samples is None else int(samples),
        "iterations": "" if iterations is None else int(iterations),
        "restarts": "" if restarts is None else int(restarts),
        "seed": int(seed),
        "score": float(result.score),
        "feasible": bool(result.constraints.hard_pass),
        "objective_cost": float(result.score_report.objective_cost),
        "constraint_penalty": float(result.score_report.constraint_penalty),
        "worst_hard_constraint": "" if worst is None else worst.name,
        "worst_hard_margin": "" if worst is None else float(worst.min_margin),
        "runtime_s": float(runtime_s),
        "robustness_cases": int(robustness_cases),
        "robust_hard_pass_rate": robustness.get("hard_pass_rate", ""),
        "robust_worst_hard_margin": robustness.get("worst_hard_margin_min", ""),
        "robust_score": robustness.get("robust_score", ""),
    }


def run_comparisons(
    aircraft_cfg: Dict[str, Any],
    spacecraft_cfg: Dict[str, Any],
    *,
    orbital_iterations: int,
    orbital_restarts: int,
    random_samples: int,
    robustness_cases: int,
    seed: int,
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    aircraft_problem = build_problem(
        with_overrides(aircraft_cfg, iterations=1, restarts=1, robustness_cases=0, seed=seed)
    )
    spacecraft_problem = build_problem(
        with_overrides(spacecraft_cfg, iterations=1, restarts=1, robustness_cases=0, seed=seed)
    )

    aircraft_orbital, runtime_s = run_orbital(
        aircraft_problem,
        aircraft_cfg,
        iterations=orbital_iterations,
        restarts=orbital_restarts,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            aircraft_cfg,
            planner_name="orbital",
            category="optimizer",
            result=aircraft_orbital,
            runtime_s=runtime_s,
            seed=seed,
            samples=None,
            iterations=orbital_iterations,
            restarts=orbital_restarts,
            robustness_cases=robustness_cases,
        )
    )

    aircraft_random, runtime_s = run_random_search(
        aircraft_problem,
        aircraft_cfg,
        samples=random_samples,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            aircraft_cfg,
            planner_name="random_search",
            category="baseline",
            result=aircraft_random,
            runtime_s=runtime_s,
            seed=seed,
            samples=random_samples,
            iterations=0,
            restarts=1,
            robustness_cases=robustness_cases,
        )
    )

    aircraft_greedy, runtime_s = run_greedy_routing(
        aircraft_problem,
        aircraft_cfg,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            aircraft_cfg,
            planner_name="greedy_routing",
            category="baseline",
            result=aircraft_greedy,
            runtime_s=runtime_s,
            seed=seed,
            samples=None,
            iterations=0,
            restarts=1,
            robustness_cases=robustness_cases,
        )
    )

    spacecraft_orbital, runtime_s = run_orbital(
        spacecraft_problem,
        spacecraft_cfg,
        iterations=orbital_iterations,
        restarts=orbital_restarts,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            spacecraft_cfg,
            planner_name="orbital",
            category="optimizer",
            result=spacecraft_orbital,
            runtime_s=runtime_s,
            seed=seed,
            samples=None,
            iterations=orbital_iterations,
            restarts=orbital_restarts,
            robustness_cases=robustness_cases,
        )
    )

    spacecraft_random, runtime_s = run_random_search(
        spacecraft_problem,
        spacecraft_cfg,
        samples=random_samples,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            spacecraft_cfg,
            planner_name="random_search",
            category="baseline",
            result=spacecraft_random,
            runtime_s=runtime_s,
            seed=seed,
            samples=random_samples,
            iterations=0,
            restarts=1,
            robustness_cases=robustness_cases,
        )
    )

    spacecraft_earliest, runtime_s = run_earliest_deadline(
        spacecraft_problem,
        spacecraft_cfg,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            spacecraft_cfg,
            planner_name="earliest_deadline",
            category="baseline",
            result=spacecraft_earliest,
            runtime_s=runtime_s,
            seed=seed,
            samples=None,
            iterations=0,
            restarts=1,
            robustness_cases=robustness_cases,
        )
    )

    return rows


def write_csv(rows: Sequence[Dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any) -> str:
    if value == "" or value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (float, int, np.floating, np.integer)):
        number = float(value)
        if not np.isfinite(number):
            return str(value)
        return f"{number:.6g}"
    return str(value)


def write_markdown(rows: Sequence[Dict[str, Any]], out_md: Path, command: str) -> None:
    lines = [
        "# Baseline Comparison Report",
        "",
        "This report compares ORBITAL against simple reference planners using the same "
        "scenario builders, simulator, objective, constraints, and robustness evaluator.",
        "",
        "Lower score is better. Feasibility means all hard constraints pass. Robust hard "
        "pass rate is measured by reevaluating the final assignment across the configured "
        "Monte Carlo cases.",
        "",
        "## Baseline Planners",
        "",
        "- `random_search`: sample random feasible decision assignments and keep the best "
        "nominal score.",
        "- `greedy_routing`: aircraft nearest-neighbor route through required waypoints.",
        "- `earliest_deadline`: spacecraft schedule observations and downlinks as early as "
        "the current decision model allows, prioritizing earliest declared deadlines.",
        "",
        "## Reproduce",
        "",
        "```bash",
        command,
        "```",
        "",
        "## Results",
        "",
        "| Domain | Planner | Score | Feasible | Runtime (s) | Robust Cases | "
        "Hard Pass Rate | Worst Robust Margin |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        lines.append(
            "| {domain} | `{planner}` | {score} | {feasible} | {runtime} | {cases} | "
            "{pass_rate} | {robust_margin} |".format(
                domain=_fmt(row["domain"]),
                planner=_fmt(row["planner"]),
                score=_fmt(row["score"]),
                feasible=_fmt(row["feasible"]),
                runtime=_fmt(row["runtime_s"]),
                cases=_fmt(row["robustness_cases"]),
                pass_rate=_fmt(row["robust_hard_pass_rate"]),
                robust_margin=_fmt(row["robust_worst_hard_margin"]),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- ORBITAL rows are solved nominally, then the final assignment is evaluated "
            "against the same robustness cases as the baselines.",
            "- Runtime includes method execution plus final robustness evaluation.",
            "- Runtime values are machine-dependent; compare scores, feasibility, and "
            "robust pass rates for deterministic checks.",
            "- The CSV file contains additional objective, penalty, and worst hard "
            "constraint fields for auditability.",
            "",
        ]
    )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def write_notes(
    out_txt: Path,
    *,
    aircraft: str,
    spacecraft: str,
    orbital_iterations: int,
    orbital_restarts: int,
    random_samples: int,
    robustness_cases: int,
    seed: int,
) -> None:
    out_txt.write_text(
        "\n".join(
            [
                "Baseline comparison runs generated by scripts/run_baselines.py",
                f"aircraft={_display_path(aircraft)}",
                f"spacecraft={_display_path(spacecraft)}",
                f"orbital_iterations={orbital_iterations}",
                f"orbital_restarts={orbital_restarts}",
                f"random_samples={random_samples}",
                f"robustness_cases={robustness_cases}",
                f"seed={seed}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _display_path(path: str) -> str:
    return Path(path).as_posix()


def build_reproduce_command(args: argparse.Namespace) -> str:
    parts = [
        "python scripts/run_baselines.py",
        f"--aircraft {_display_path(args.aircraft)}",
        f"--spacecraft {_display_path(args.spacecraft)}",
        f"--out {_display_path(args.out)}",
        f"--orbital-iterations {args.orbital_iterations}",
        f"--orbital-restarts {args.orbital_restarts}",
        f"--random-samples {args.random_samples}",
        f"--robustness-cases {args.robustness_cases}",
        f"--seed {args.seed}",
    ]
    return " ".join(parts)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ORBITAL baseline comparison reports.")
    parser.add_argument("--aircraft", default=DEFAULT_AIRCRAFT_SCENARIO, type=str)
    parser.add_argument("--spacecraft", default=DEFAULT_SPACECRAFT_SCENARIO, type=str)
    parser.add_argument("--out", default=DEFAULT_OUTPUT_CSV, type=str)
    parser.add_argument("--markdown-out", default=None, type=str)
    parser.add_argument("--seed", default=0, type=int, help="Master seed for all comparisons.")
    parser.add_argument("--orbital-iterations", "--orbital_iterations", default=200, type=int)
    parser.add_argument("--orbital-restarts", "--orbital_restarts", default=1, type=int)
    parser.add_argument(
        "--random-samples",
        "--spacecraft_baseline_restarts",
        default=50,
        type=int,
        help="Number of random feasible assignments to sample in random_search.",
    )
    parser.add_argument(
        "--robustness-cases",
        "--orbital_robustness",
        default=5,
        type=int,
        help="Monte Carlo cases used to evaluate each final assignment.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    out_csv = Path(args.out)
    out_md = Path(args.markdown_out) if args.markdown_out else out_csv.parent / "baselines.md"
    note_path = out_csv.parent / "README.txt"

    aircraft_cfg = load_yaml(Path(args.aircraft))
    spacecraft_cfg = load_yaml(Path(args.spacecraft))

    rows = run_comparisons(
        aircraft_cfg,
        spacecraft_cfg,
        orbital_iterations=args.orbital_iterations,
        orbital_restarts=args.orbital_restarts,
        random_samples=args.random_samples,
        robustness_cases=args.robustness_cases,
        seed=args.seed,
    )

    command = build_reproduce_command(args)
    write_csv(rows, out_csv)
    write_markdown(rows, out_md, command)
    write_notes(
        note_path,
        aircraft=args.aircraft,
        spacecraft=args.spacecraft,
        orbital_iterations=args.orbital_iterations,
        orbital_restarts=args.orbital_restarts,
        random_samples=args.random_samples,
        robustness_cases=args.robustness_cases,
        seed=args.seed,
    )

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
