#!/usr/bin/env python3
"""
ORBITAL Seed-Run Experiment Harness

Runs multiple seeds for one or more scenarios using the existing CLI and writes:
- CSV summary (score, feasible, worst hard margin, runtime)
- Raw logs per run

Example:
  python experiments/run_seed_experiments.py \
    --aircraft examples/aircraft_uav_demo.yaml \
    --spacecraft examples/cubesat_leo_demo.yaml \
    --seeds 20 \
    --iterations 200 \
    --restarts 1 \
    --robustness 0 \
    --out results/seed_runs.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple, List

# ----------------------------
# Parsing helpers
# ----------------------------

SCORE_RE = re.compile(r"^\s*Score:\s*([+-]?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
FEAS_RE = re.compile(r"^\s*Feasible:\s*(True|False)\s*$", re.IGNORECASE)
WORST_RE = re.compile(
    r"^\s*Worst\s+HARD\s+margin:\s*([+-]?\d+(?:\.\d+)?)(?:\s*\(([^)]+)\))?\s*$",
    re.IGNORECASE,
)


@dataclass
class RunResult:
    scenario_label: str
    scenario_path: str
    seed: int
    iterations: int
    restarts: int
    robustness: int

    score: Optional[float]
    feasible: Optional[bool]
    worst_hard_margin: Optional[float]
    worst_hard_constraint: Optional[str]

    runtime_sec: float
    returncode: int
    log_path: str


def parse_cli_output(
    stdout: str,
) -> Tuple[Optional[float], Optional[bool], Optional[float], Optional[str]]:
    """
    Extract key metrics from ORBITAL CLI output.
    Expected lines (based on your CLI printout):
      Score:    311.891
      Feasible: True
      Worst HARD margin: +0.0922964 (bank_angle_turn_limit)
    """
    score = None
    feasible = None
    worst_margin = None
    worst_name = None

    for line in stdout.splitlines():
        m = SCORE_RE.match(line)
        if m:
            score = float(m.group(1))
            continue

        m = FEAS_RE.match(line)
        if m:
            feasible = m.group(1).lower() == "true"
            continue

        m = WORST_RE.match(line)
        if m:
            worst_margin = float(m.group(1))
            worst_name = m.group(2).strip() if m.group(2) else None
            continue

    return score, feasible, worst_margin, worst_name


# ----------------------------
# Runner
# ----------------------------


def run_one(
    scenario_label: str,
    scenario_path: Path,
    seed: int,
    iterations: int,
    restarts: int,
    robustness: int,
    logs_dir: Path,
) -> RunResult:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{scenario_label}_seed{seed:04d}.txt"

    cmd: List[str] = [
        sys.executable,
        "-m",
        "mission_framework.cli",
        str(scenario_path),
        "--iterations",
        str(iterations),
        "--restarts",
        str(restarts),
        "--robustness",
        str(robustness),
        "--seed",
        str(seed),  # IMPORTANT: assumes your CLI supports --seed
    ]

    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    t1 = time.perf_counter()

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout + ("\n\n--- STDERR ---\n" + stderr if stderr.strip() else "")

    log_path.write_text(combined, encoding="utf-8")

    score, feasible, worst_margin, worst_name = parse_cli_output(stdout)

    return RunResult(
        scenario_label=scenario_label,
        scenario_path=str(scenario_path),
        seed=seed,
        iterations=iterations,
        restarts=restarts,
        robustness=robustness,
        score=score,
        feasible=feasible,
        worst_hard_margin=worst_margin,
        worst_hard_constraint=worst_name,
        runtime_sec=float(t1 - t0),
        returncode=int(proc.returncode),
        log_path=str(log_path),
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aircraft", type=str, default=None, help="Path to aircraft YAML scenario")
    p.add_argument("--spacecraft", type=str, default=None, help="Path to spacecraft YAML scenario")

    p.add_argument("--seeds", type=int, default=20, help="Number of seeds to run per scenario")
    p.add_argument("--seed_start", type=int, default=0, help="Starting seed value")

    p.add_argument("--iterations", type=int, default=200, help="Planner iterations")
    p.add_argument("--restarts", type=int, default=1, help="Planner restarts")
    p.add_argument("--robustness", type=int, default=0, help="Robustness cases (0 disables)")

    p.add_argument("--out", type=str, default="results/seed_runs.csv", help="Output CSV path")
    p.add_argument("--results_dir", type=str, default="results", help="Results folder")
    args = p.parse_args()

    scenarios = []
    if args.aircraft:
        scenarios.append(("aircraft", Path(args.aircraft)))
    if args.spacecraft:
        scenarios.append(("spacecraft", Path(args.spacecraft)))

    if not scenarios:
        print("ERROR: Provide at least --aircraft or --spacecraft scenario YAML.", file=sys.stderr)
        return 2

    results_dir = Path(args.results_dir)
    logs_dir = results_dir / "logs"
    results_dir.mkdir(parents=True, exist_ok=True)

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    all_rows: List[RunResult] = []

    for label, path in scenarios:
        if not path.exists():
            print(f"ERROR: scenario file not found: {path}", file=sys.stderr)
            return 2

        for i in range(args.seeds):
            seed = args.seed_start + i
            print(f"[run] {label} seed={seed} ...")
            rr = run_one(
                scenario_label=label,
                scenario_path=path,
                seed=seed,
                iterations=args.iterations,
                restarts=args.restarts,
                robustness=args.robustness,
                logs_dir=logs_dir,
            )
            all_rows.append(rr)

            # quick console feedback if parsing failed
            if rr.score is None or rr.feasible is None or rr.worst_hard_margin is None:
                print(
                    f"  WARN: Could not parse one or more metrics from stdout. See log: {rr.log_path}"
                )

    # Write CSV
    fieldnames = list(asdict(all_rows[0]).keys()) if all_rows else []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rr in all_rows:
            w.writerow(asdict(rr))

    # Write a lightweight summary JSON (optional but judge-friendly)
    summary = {
        "runs": len(all_rows),
        "scenarios": sorted(list({r.scenario_label for r in all_rows})),
        "notes": [
            "feasible indicates whether hard constraints passed (as reported by CLI).",
            "worst_hard_margin is the minimum hard constraint margin (>=0 is feasible).",
            "logs saved in results/logs/ for reproducibility.",
        ],
    }
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nDone. Wrote: {out_csv}")
    print(f"Logs: {logs_dir}")
    print(f"Summary: {results_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
