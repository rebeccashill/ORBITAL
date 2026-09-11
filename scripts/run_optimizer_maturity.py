#!/usr/bin/env python3
"""
Generate optimizer maturity benchmark reports for ORBITAL.

This report is intentionally broader than scripts/run_baselines.py:
- it runs both demo and stress scenarios;
- it compares ORBITAL with random/simple heuristic baselines; and
- it adds an exhaustive_grid baseline for small discretized decision spaces.

The exhaustive grid is not a production solver. It is a practical, auditable
solver-style comparison for the small aircraft and spacecraft scenarios checked
into this repository.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mission_framework.core.constraints import Severity  # noqa: E402
from mission_framework.core.decision_variables import DecisionAssignment  # noqa: E402
from mission_framework.core.solutions import PlanResult  # noqa: E402
from scripts.run_baselines import (  # noqa: E402
    build_problem,
    evaluate_assignment,
    load_yaml,
    run_earliest_deadline,
    run_greedy_routing,
    run_orbital,
    run_random_search,
    scenario_name,
    scenario_type,
    with_overrides,
)

DEFAULT_SCENARIOS = [
    "examples/aircraft_uav_demo.yaml",
    "examples/cubesat_leo_demo.yaml",
    "examples/stress/aircraft_high_wind.yaml",
    "examples/stress/aircraft_low_battery_tight_nfzs.yaml",
    "examples/stress/spacecraft_power_starved.yaml",
    "examples/stress/spacecraft_slew-constrained.yaml",
]
DEFAULT_OUTPUT_CSV = "outputs/validation/optimizer_maturity/optimizer_maturity.csv"

FIELDNAMES = [
    "scenario_group",
    "domain",
    "scenario",
    "scenario_file",
    "planner",
    "category",
    "candidate_evaluations",
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
    "notes",
]


def scenario_group(path: Path) -> str:
    """Return a report grouping label for demo versus stress scenarios."""
    return "stress" if "stress" in path.parts else "demo"


def aircraft_exhaustive_assignments(
    cfg: Dict[str, Any],
    *,
    speed_grid: int,
) -> list[DecisionAssignment]:
    """Enumerate all aircraft waypoint permutations over a cruise-speed grid."""
    if speed_grid < 1:
        raise ValueError("speed_grid must be at least 1.")

    waypoints = (cfg.get("mission", {}) or {}).get("waypoints", []) or []
    waypoint_ids = [str(wp.get("id", "")) for wp in waypoints]
    if not waypoint_ids:
        raise ValueError("aircraft exhaustive grid requires mission.waypoints.")

    vehicle = cfg.get("vehicle", {}) or {}
    min_speed = float(vehicle.get("min_speed_mps", 12.0))
    max_speed = float(vehicle.get("max_speed_mps", 30.0))
    speeds = np.linspace(min_speed, max_speed, num=speed_grid, dtype=float)

    assignments: list[DecisionAssignment] = []
    for order in itertools.permutations(waypoint_ids):
        for speed in speeds:
            assignments.append(
                DecisionAssignment(
                    {
                        "visit_order": list(order),
                        "cruise_speed_mps": np.array([float(speed)], dtype=float),
                    }
                )
            )
    return assignments


def _target_ids(cfg: Dict[str, Any]) -> list[str]:
    targets = (cfg.get("mission", {}) or {}).get("targets", []) or []
    target_ids = [str(target.get("id", "")) for target in targets]
    if not target_ids:
        raise ValueError("spacecraft exhaustive grid requires mission.targets.")
    return target_ids


def spacecraft_exhaustive_assignments(
    cfg: Dict[str, Any],
    *,
    offset_grid: int,
) -> list[DecisionAssignment]:
    """Enumerate target selections, observation offsets, and downlink policies."""
    if offset_grid < 1:
        raise ValueError("offset_grid must be at least 1.")

    target_ids = _target_ids(cfg)
    offsets = np.linspace(0.0, 1.0, num=offset_grid, dtype=float)
    assignments: list[DecisionAssignment] = []

    for select_bits in itertools.product([0, 1], repeat=len(target_ids)):
        selected_count = int(sum(select_bits))
        for selected_offsets in itertools.product(offsets, repeat=selected_count):
            for downlink_policy in [0, 1, 2]:
                offset_by_target = iter(selected_offsets)
                values: Dict[str, Any] = {"downlink_policy": int(downlink_policy)}
                for target_id, selected in zip(target_ids, select_bits):
                    values[f"select_{target_id}"] = int(selected)
                    offset = float(next(offset_by_target)) if selected else 0.0
                    values[f"obs_offset_{target_id}"] = np.array([offset], dtype=float)

                assignments.append(DecisionAssignment(values))

    return assignments


def exhaustive_assignments(
    cfg: Dict[str, Any],
    *,
    speed_grid: int,
    offset_grid: int,
) -> list[DecisionAssignment]:
    domain = scenario_type(cfg)
    if domain == "aircraft":
        return aircraft_exhaustive_assignments(cfg, speed_grid=speed_grid)
    if domain == "spacecraft":
        return spacecraft_exhaustive_assignments(cfg, offset_grid=offset_grid)
    raise ValueError(f"Unsupported scenario type for exhaustive grid: {domain}")


def run_exhaustive_grid(
    cfg: Dict[str, Any],
    *,
    speed_grid: int,
    offset_grid: int,
    max_candidates: int,
    robustness_cases: int,
    seed: int,
) -> tuple[PlanResult, float, int, str]:
    """Evaluate every candidate in the small discretized decision grid."""
    candidates = exhaustive_assignments(cfg, speed_grid=speed_grid, offset_grid=offset_grid)
    if len(candidates) > max_candidates:
        raise ValueError(
            "exhaustive_grid would evaluate "
            f"{len(candidates)} candidates, above max_candidates={max_candidates}."
        )

    problem = build_problem(with_overrides(cfg, robustness_cases=0, seed=seed))
    rng = np.random.default_rng(seed)
    best: Optional[PlanResult] = None

    t0 = time.perf_counter()
    for candidate in candidates:
        result = evaluate_assignment(
            problem,
            cfg,
            candidate,
            seed=int(rng.integers(0, 2**31 - 1)),
            robustness_cases=0,
        )
        if best is None or result.score < best.score:
            best = result

    if best is None:
        raise RuntimeError("exhaustive_grid did not evaluate any candidates.")

    final_result = evaluate_assignment(
        problem,
        cfg,
        best.assignment,
        seed=seed,
        robustness_cases=robustness_cases,
    )
    runtime_s = time.perf_counter() - t0
    note = (
        f"Enumerated {len(candidates)} candidates "
        f"(speed_grid={speed_grid}, offset_grid={offset_grid})."
    )
    return final_result, runtime_s, len(candidates), note


def row_for_result(
    cfg: Dict[str, Any],
    path: Path,
    *,
    planner_name: str,
    category: str,
    result: PlanResult,
    runtime_s: float,
    candidate_evaluations: int,
    robustness_cases: int,
    notes: str = "",
) -> Dict[str, Any]:
    worst = result.constraints.worst(Severity.HARD)
    robustness = result.robustness or {}

    return {
        "scenario_group": scenario_group(path),
        "domain": scenario_type(cfg),
        "scenario": scenario_name(cfg),
        "scenario_file": path.as_posix(),
        "planner": planner_name,
        "category": category,
        "candidate_evaluations": int(candidate_evaluations),
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
        "notes": notes,
    }


def run_scenario(
    path: Path,
    *,
    orbital_iterations: int,
    orbital_restarts: int,
    random_samples: int,
    robustness_cases: int,
    speed_grid: int,
    offset_grid: int,
    max_exhaustive_candidates: int,
    seed: int,
) -> list[Dict[str, Any]]:
    cfg = load_yaml(path)
    problem = build_problem(with_overrides(cfg, robustness_cases=0, seed=seed))
    domain = scenario_type(cfg)
    rows: list[Dict[str, Any]] = []

    orbital_result, runtime_s = run_orbital(
        problem,
        cfg,
        iterations=orbital_iterations,
        restarts=orbital_restarts,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            cfg,
            path,
            planner_name="orbital",
            category="optimizer",
            result=orbital_result,
            runtime_s=runtime_s,
            candidate_evaluations=orbital_iterations * orbital_restarts,
            robustness_cases=robustness_cases,
            notes="Shared stochastic local-search planner.",
        )
    )

    random_result, runtime_s = run_random_search(
        problem,
        cfg,
        samples=random_samples,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            cfg,
            path,
            planner_name="random_search",
            category="baseline",
            result=random_result,
            runtime_s=runtime_s,
            candidate_evaluations=random_samples,
            robustness_cases=robustness_cases,
            notes="Random feasible assignments, best nominal score retained.",
        )
    )

    if domain == "aircraft":
        simple_result, runtime_s = run_greedy_routing(
            problem,
            cfg,
            robustness_cases=robustness_cases,
            seed=seed,
        )
        simple_name = "greedy_routing"
        simple_note = "Nearest-neighbor waypoint routing."
    elif domain == "spacecraft":
        simple_result, runtime_s = run_earliest_deadline(
            problem,
            cfg,
            robustness_cases=robustness_cases,
            seed=seed,
        )
        simple_name = "earliest_deadline"
        simple_note = "Earliest target deadlines with earliest downlink placement."
    else:
        raise ValueError(f"Unsupported scenario type: {domain}")

    rows.append(
        row_for_result(
            cfg,
            path,
            planner_name=simple_name,
            category="baseline",
            result=simple_result,
            runtime_s=runtime_s,
            candidate_evaluations=1,
            robustness_cases=robustness_cases,
            notes=simple_note,
        )
    )

    exhaustive_result, runtime_s, candidate_count, exhaustive_note = run_exhaustive_grid(
        cfg,
        speed_grid=speed_grid,
        offset_grid=offset_grid,
        max_candidates=max_exhaustive_candidates,
        robustness_cases=robustness_cases,
        seed=seed,
    )
    rows.append(
        row_for_result(
            cfg,
            path,
            planner_name="exhaustive_grid",
            category="solver_style",
            result=exhaustive_result,
            runtime_s=runtime_s,
            candidate_evaluations=candidate_count,
            robustness_cases=robustness_cases,
            notes=exhaustive_note,
        )
    )

    return rows


def run_benchmarks(
    scenario_paths: Sequence[Path],
    *,
    orbital_iterations: int,
    orbital_restarts: int,
    random_samples: int,
    robustness_cases: int,
    speed_grid: int,
    offset_grid: int,
    max_exhaustive_candidates: int,
    seed: int,
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for index, path in enumerate(scenario_paths):
        rows.extend(
            run_scenario(
                path,
                orbital_iterations=orbital_iterations,
                orbital_restarts=orbital_restarts,
                random_samples=random_samples,
                robustness_cases=robustness_cases,
                speed_grid=speed_grid,
                offset_grid=offset_grid,
                max_exhaustive_candidates=max_exhaustive_candidates,
                seed=seed + index * 1009,
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


def _best_rows_by_scenario(rows: Sequence[Dict[str, Any]]) -> list[Dict[str, Any]]:
    best: dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row["scenario_file"])
        current = best.get(key)
        if current is None or float(row["score"]) < float(current["score"]):
            best[key] = row
    return [best[key] for key in sorted(best)]


def write_markdown(rows: Sequence[Dict[str, Any]], out_md: Path, command: str) -> None:
    lines = [
        "# Optimizer Maturity Benchmark Report",
        "",
        "This report broadens ORBITAL's optimizer evidence beyond the two demo scenarios. "
        "It runs demo and stress YAML files through the shared simulator, objective, "
        "constraints, and robustness evaluator, then compares ORBITAL against simple "
        "baselines and a small exhaustive_grid solver-style baseline.",
        "",
        "The optimizer is strong demo and research engineering, but it is not yet "
        "production-grade mission planning. Treat these numbers as reproducible evidence "
        "for the checked-in models, not as validation against established flight or "
        "operations planning tools.",
        "",
        "## Compared Planners",
        "",
        "- `orbital`: shared stochastic local-search planner.",
        "- `random_search`: random feasible decision assignments, best nominal score kept.",
        "- `greedy_routing`: aircraft nearest-neighbor waypoint route.",
        "- `earliest_deadline`: spacecraft observations ordered by declared deadlines.",
        "- `exhaustive_grid`: enumerates the small discretized decision grid used by the "
        "checked-in scenarios. It is solver-style and auditable, but not a continuous "
        "global optimizer.",
        "",
        "## Reproduce",
        "",
        "```bash",
        command,
        "```",
        "",
        "## Best Planner By Scenario",
        "",
        "| Group | Domain | Scenario | Best Planner | Score | Feasible | Robust Pass Rate |",
        "| --- | --- | --- | --- | ---: | --- | ---: |",
    ]

    for row in _best_rows_by_scenario(rows):
        lines.append(
            "| {group} | {domain} | {scenario} | `{planner}` | {score} | {feasible} | "
            "{pass_rate} |".format(
                group=_fmt(row["scenario_group"]),
                domain=_fmt(row["domain"]),
                scenario=_fmt(row["scenario"]),
                planner=_fmt(row["planner"]),
                score=_fmt(row["score"]),
                feasible=_fmt(row["feasible"]),
                pass_rate=_fmt(row["robust_hard_pass_rate"]),
            )
        )

    lines.extend(
        [
            "",
            "## Full Results",
            "",
            "| Group | Domain | Scenario | Planner | Category | Candidates | Score | Feasible | "
            "Runtime (s) | Robust Pass Rate | Worst Robust Margin |",
            "| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
        ]
    )

    for row in rows:
        lines.append(
            "| {group} | {domain} | {scenario} | `{planner}` | {category} | {candidates} | "
            "{score} | {feasible} | {runtime} | {pass_rate} | {robust_margin} |".format(
                group=_fmt(row["scenario_group"]),
                domain=_fmt(row["domain"]),
                scenario=_fmt(row["scenario"]),
                planner=_fmt(row["planner"]),
                category=_fmt(row["category"]),
                candidates=_fmt(row["candidate_evaluations"]),
                score=_fmt(row["score"]),
                feasible=_fmt(row["feasible"]),
                runtime=_fmt(row["runtime_s"]),
                pass_rate=_fmt(row["robust_hard_pass_rate"]),
                robust_margin=_fmt(row["robust_worst_hard_margin"]),
            )
        )

    lines.extend(
        [
            "",
            "## Maturity Readout",
            "",
            "- This expands stress evidence by running the high-wind, tight-geofence, "
            "power-starved, and slew-constrained scenarios in one reproducible matrix.",
            "- `exhaustive_grid` gives a stronger small-problem comparison than random "
            "or single-pass greedy heuristics where enumeration is practical.",
            "- Matching or trailing `exhaustive_grid` on a checked-in scenario should be "
            "read as useful calibration, not failure: the grid has scenario-specific "
            "knowledge and can afford full enumeration at this small scale.",
            "- The current spacecraft examples are still proxy-heavy and relatively easy. "
            "A production-grade claim would need comparisons against established orbital "
            "or mission-planning methods, clearer physical assumptions, richer benchmark "
            "scenarios, and at least one genuinely hard scheduling case.",
            "",
        ]
    )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def write_notes(
    out_txt: Path,
    *,
    scenario_paths: Sequence[Path],
    orbital_iterations: int,
    orbital_restarts: int,
    random_samples: int,
    robustness_cases: int,
    speed_grid: int,
    offset_grid: int,
    max_exhaustive_candidates: int,
    seed: int,
) -> None:
    out_txt.write_text(
        "\n".join(
            [
                "Optimizer maturity benchmark generated by scripts/run_optimizer_maturity.py",
                "scenarios:",
                *[f"- {path.as_posix()}" for path in scenario_paths],
                f"orbital_iterations={orbital_iterations}",
                f"orbital_restarts={orbital_restarts}",
                f"random_samples={random_samples}",
                f"robustness_cases={robustness_cases}",
                f"speed_grid={speed_grid}",
                f"offset_grid={offset_grid}",
                f"max_exhaustive_candidates={max_exhaustive_candidates}",
                f"seed={seed}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_reproduce_command(args: argparse.Namespace, scenario_paths: Sequence[Path]) -> str:
    scenario_args = " ".join(f"--scenario {path.as_posix()}" for path in scenario_paths)
    parts = [
        "python scripts/run_optimizer_maturity.py",
        scenario_args,
        f"--out {Path(args.out).as_posix()}",
        f"--orbital-iterations {args.orbital_iterations}",
        f"--orbital-restarts {args.orbital_restarts}",
        f"--random-samples {args.random_samples}",
        f"--robustness-cases {args.robustness_cases}",
        f"--speed-grid {args.speed_grid}",
        f"--offset-grid {args.offset_grid}",
        f"--max-exhaustive-candidates {args.max_exhaustive_candidates}",
        f"--seed {args.seed}",
    ]
    return " ".join(part for part in parts if part)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate ORBITAL optimizer maturity benchmark reports."
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Scenario YAML to include. Repeat to override the default demo/stress matrix.",
    )
    parser.add_argument("--out", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--markdown-out", default=None)
    parser.add_argument("--seed", default=0, type=int)
    parser.add_argument("--orbital-iterations", default=120, type=int)
    parser.add_argument("--orbital-restarts", default=1, type=int)
    parser.add_argument("--random-samples", default=25, type=int)
    parser.add_argument("--robustness-cases", default=3, type=int)
    parser.add_argument("--speed-grid", default=5, type=int)
    parser.add_argument("--offset-grid", default=3, type=int)
    parser.add_argument("--max-exhaustive-candidates", default=5000, type=int)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    scenario_paths = [Path(path) for path in (args.scenario or DEFAULT_SCENARIOS)]
    out_csv = Path(args.out)
    out_md = (
        Path(args.markdown_out) if args.markdown_out else out_csv.parent / "optimizer_maturity.md"
    )
    out_txt = out_csv.parent / "README.txt"

    rows = run_benchmarks(
        scenario_paths,
        orbital_iterations=args.orbital_iterations,
        orbital_restarts=args.orbital_restarts,
        random_samples=args.random_samples,
        robustness_cases=args.robustness_cases,
        speed_grid=args.speed_grid,
        offset_grid=args.offset_grid,
        max_exhaustive_candidates=args.max_exhaustive_candidates,
        seed=args.seed,
    )
    command = build_reproduce_command(args, scenario_paths)

    write_csv(rows, out_csv)
    write_markdown(rows, out_md, command)
    write_notes(
        out_txt,
        scenario_paths=scenario_paths,
        orbital_iterations=args.orbital_iterations,
        orbital_restarts=args.orbital_restarts,
        random_samples=args.random_samples,
        robustness_cases=args.robustness_cases,
        speed_grid=args.speed_grid,
        offset_grid=args.offset_grid,
        max_exhaustive_candidates=args.max_exhaustive_candidates,
        seed=args.seed,
    )

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
