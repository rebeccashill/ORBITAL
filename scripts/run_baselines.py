#!/usr/bin/env python3
"""
Baseline comparisons for AeroHack rubric.

Runs:
- ORBITAL (normal planner settings)
- Aircraft baseline: random feasible (iterations=0, restarts=1)
- Spacecraft baseline: multi-start sampling (iterations=0, restarts=K) as a "greedy-ish" best-of-K baseline

Outputs:
- outputs/validation/baselines/baselines.csv
- outputs/validation/baselines/README.txt (what was run)

Usage (PowerShell one-liner):
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --out outputs/validation/baselines/baselines.csv
"""

from __future__ import annotations

import argparse
import csv
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.planner import Planner, PlannerConfig, Severity
from mission_framework.core.objective import RobustAggregation
from mission_framework.aircraft.mission import build_problem_from_config as build_aircraft
from mission_framework.spacecraft.mission import build_problem_from_config as build_spacecraft


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_cfg_overrides(
    cfg: Dict[str, Any], *, iterations: int, restarts: int, robustness_cases: int, seed: int
) -> Dict[str, Any]:
    cfg = deepcopy(cfg)
    cfg.setdefault("planner", {})
    cfg["planner"]["iterations"] = int(iterations)
    cfg["planner"]["restarts"] = int(restarts)
    cfg["planner"]["seed"] = int(seed)
    cfg.setdefault("robustness", {})
    cfg["robustness"]["cases"] = int(robustness_cases)
    return cfg


def build_problem(cfg: Dict[str, Any]):
    stype = (cfg.get("scenario", {}) or {}).get("type", "").strip().lower()
    if stype == "aircraft":
        return build_aircraft(cfg)
    if stype == "spacecraft":
        return build_spacecraft(cfg)
    raise ValueError(f"Unknown scenario.type={stype!r}")


def run_once(label: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Build Problem
    problem = build_problem(cfg)

    # Robustness settings (if present)
    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    # Optional robust aggregation
    agg = (rob.get("aggregation") or "").strip().lower()
    if agg in ("mean", "worst", "cvar"):
        problem.robust_aggregation = RobustAggregation(agg)
    if "cvar_alpha" in rob:
        problem.cvar_alpha = float(rob["cvar_alpha"])

    # Planner config from cfg
    p = cfg.get("planner", {}) or {}
    planner_cfg = PlannerConfig(
        iterations=int(p.get("iterations", 200)),
        restarts=int(p.get("restarts", 1)),
        hard_infeasible_penalty=float(p.get("hard_infeasible_penalty", 1e6)),
        seed=int(p.get("seed", 0)),
        keep_history=False,
    )

    t0 = time.perf_counter()
    result = Planner(planner_cfg).solve(problem)
    t1 = time.perf_counter()

    worst = result.constraints.worst(Severity.HARD)
    worst_margin = float(worst.min_margin) if worst is not None else None
    worst_name = worst.name if worst is not None else None

    return {
        "label": label,
        "scenario_name": (cfg.get("scenario", {}) or {}).get("name", ""),
        "scenario_type": (cfg.get("scenario", {}) or {}).get("type", ""),
        "iterations": planner_cfg.iterations,
        "restarts": planner_cfg.restarts,
        "robustness_cases": int(problem.robustness_cases),
        "seed": planner_cfg.seed,
        "score": float(result.score),
        "feasible": bool(result.constraints.hard_pass),
        "worst_hard_margin": worst_margin,
        "worst_hard_constraint": worst_name,
        "runtime_sec": float(t1 - t0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aircraft", required=True, type=str)
    ap.add_argument("--spacecraft", required=True, type=str)
    ap.add_argument("--out", default="outputs/validation/baselines/baselines.csv", type=str)
    ap.add_argument("--seed", default=0, type=int, help="Master seed for baseline comparisons")
    ap.add_argument("--orbital_iterations", default=200, type=int)
    ap.add_argument("--orbital_restarts", default=1, type=int)
    ap.add_argument("--orbital_robustness", default=0, type=int)

    ap.add_argument(
        "--spacecraft_baseline_restarts",
        default=50,
        type=int,
        help="Best-of-K sampling for spacecraft baseline (iterations=0, restarts=K)",
    )
    args = ap.parse_args()

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    note_path = out_csv.parent / "README.txt"

    aircraft_cfg0 = load_yaml(Path(args.aircraft))
    spacecraft_cfg0 = load_yaml(Path(args.spacecraft))

    rows = []

    # ORBITAL (aircraft)
    rows.append(
        run_once(
            "ORBITAL (aircraft)",
            ensure_cfg_overrides(
                aircraft_cfg0,
                iterations=args.orbital_iterations,
                restarts=args.orbital_restarts,
                robustness_cases=args.orbital_robustness,
                seed=args.seed,
            ),
        )
    )

    # Aircraft baseline: single random feasible (no optimization)
    rows.append(
        run_once(
            "Baseline: Random feasible (aircraft)",
            ensure_cfg_overrides(
                aircraft_cfg0,
                iterations=0,
                restarts=1,
                robustness_cases=0,
                seed=args.seed,
            ),
        )
    )

    # ORBITAL (spacecraft)
    rows.append(
        run_once(
            "ORBITAL (spacecraft)",
            ensure_cfg_overrides(
                spacecraft_cfg0,
                iterations=args.orbital_iterations,
                restarts=args.orbital_restarts,
                robustness_cases=args.orbital_robustness,
                seed=args.seed,
            ),
        )
    )

    # Spacecraft baseline: best-of-K sampling (iterations=0, restarts=K)
    rows.append(
        run_once(
            f"Baseline: Best-of-{args.spacecraft_baseline_restarts} sampling (spacecraft)",
            ensure_cfg_overrides(
                spacecraft_cfg0,
                iterations=0,
                restarts=args.spacecraft_baseline_restarts,
                robustness_cases=0,
                seed=args.seed,
            ),
        )
    )

    # Write CSV
    fieldnames = list(rows[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Write notes for judges
    note_path.write_text(
        "Baseline comparison runs generated by scripts/run_baselines.py\n"
        f"aircraft={args.aircraft}\nspacecraft={args.spacecraft}\n"
        f"orbital_iterations={args.orbital_iterations}\norbital_restarts={args.orbital_restarts}\n"
        f"orbital_robustness={args.orbital_robustness}\nseed={args.seed}\n"
        f"spacecraft_baseline_restarts={args.spacecraft_baseline_restarts}\n",
        encoding="utf-8",
    )

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
