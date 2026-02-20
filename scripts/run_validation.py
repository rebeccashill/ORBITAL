#!/usr/bin/env python3
"""
AeroHack Validation Script

Runs:
- Monte Carlo robustness on baseline aircraft/spacecraft demos
- Stress-case YAMLs for both domains
- Saves logs and preserves failure cases (nonzero exit or Feasible: False)

Outputs:
outputs/validation/
  aircraft/<case_name>/*
  spacecraft/<case_name>/*
  logs/<case_name>.txt
  validation_summary.json
"""

import subprocess
import json
import sys
import re
from pathlib import Path
import shutil
from typing import Dict, Any, Tuple, Optional

FEASIBLE_RE = re.compile(r"^\s*Feasible:\s*(True|False)\s*$", re.MULTILINE)


def parse_feasible(stdout: str) -> Optional[bool]:
    m = FEASIBLE_RE.search(stdout or "")
    if not m:
        return None
    return m.group(1) == "True"


def copy_run_artifacts(run_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not run_dir.exists():
        return
    for ext in ("*.json", "*.csv", "*.png"):
        for f in run_dir.glob(ext):
            shutil.copy(f, dest_dir / f.name)


def run_case(
    case_name: str, yaml_path: str, *, iterations: int, restarts: int, robustness: int, seed: int
) -> Dict[str, Any]:
    """
    Runs a single case, captures logs, copies artifacts, and labels failures.
    Uses --outdir runs so per-yaml stem maps to runs/<stem>/.
    """
    print(f"\n{'='*70}")
    print(f"RUN CASE: {case_name}")
    print(f"YAML: {yaml_path}")
    print(f"{'='*70}\n")

    cmd = [
        sys.executable,
        "-m",
        "mission_framework.cli",
        yaml_path,
        "--iterations",
        str(iterations),
        "--restarts",
        str(restarts),
        "--robustness",
        str(robustness),
        "--seed",
        str(seed),
        "--outdir",
        "runs",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    # Always save a combined log
    logs_dir = Path("outputs/validation/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{case_name}.txt"
    log_path.write_text(
        f"CMD: {' '.join(cmd)}\n\n--- STDOUT ---\n{stdout}\n\n--- STDERR ---\n{stderr}\n",
        encoding="utf-8",
    )

    print(stdout)
    if result.returncode != 0:
        print(f"ERROR (nonzero exit): {stderr}", file=sys.stderr)

    feasible = parse_feasible(stdout)

    yaml_stem = Path(yaml_path).stem
    run_dir = Path("runs") / yaml_stem

    # Decide output folder: keep failures in a dedicated subdir
    domain = "aircraft" if "aircraft" in yaml_path or "UAV" in stdout else "spacecraft"
    base_out = Path("outputs/validation") / domain / case_name

    copy_run_artifacts(run_dir, base_out)

    is_failure = (result.returncode != 0) or (feasible is False)

    # Preserve failure case snapshot (same artifacts + log reference)
    failure_dir = None
    if is_failure:
        failure_dir = Path("outputs/validation") / "failures" / domain / case_name
        copy_run_artifacts(run_dir, failure_dir)
        # also copy log
        shutil.copy(log_path, failure_dir / "run_log.txt")

    return {
        "case_name": case_name,
        "yaml": yaml_path,
        "domain": domain,
        "iterations": iterations,
        "restarts": restarts,
        "robustness_cases": robustness,
        "seed": seed,
        "returncode": result.returncode,
        "feasible": feasible,
        "log_path": str(log_path),
        "artifacts_dir": str(base_out),
        "failure_dir": str(failure_dir) if failure_dir else None,
    }


def main() -> int:
    print("""
╔══════════════════════════════════════════════════════════╗
║          AEROHACK VALIDATION - ROBUST + STRESS           ║
╚══════════════════════════════════════════════════════════╝
""")

    summary = {"cases": []}

    # Baseline Monte Carlo runs (as before, but now as cases)
    summary["cases"].append(
        run_case(
            "baseline_aircraft_monte_carlo",
            "examples/aircraft_uav_demo.yaml",
            iterations=500,
            restarts=2,
            robustness=50,
            seed=0,
        )
    )

    summary["cases"].append(
        run_case(
            "baseline_spacecraft_monte_carlo",
            "examples/cubesat_leo_demo.yaml",
            iterations=300,
            restarts=2,
            robustness=30,
            seed=0,
        )
    )

    # Stress cases (2 per domain)
    summary["cases"].append(
        run_case(
            "stress_aircraft_high_wind",
            "examples/stress/aircraft_high_wind.yaml",
            iterations=600,
            restarts=3,
            robustness=30,
            seed=0,
        )
    )

    summary["cases"].append(
        run_case(
            "stress_aircraft_low_battery_tight_nfzs",
            "examples/stress/aircraft_low_battery_tight_nfzs.yaml",
            iterations=800,
            restarts=3,
            robustness=20,
            seed=0,
        )
    )

    summary["cases"].append(
        run_case(
            "stress_spacecraft_power_starved",
            "examples/stress/spacecraft_power_starved.yaml",
            iterations=600,
            restarts=3,
            robustness=20,
            seed=0,
        )
    )

    summary["cases"].append(
        run_case(
            "stress_spacecraft_slew_constrained",
            "examples/stress/spacecraft_slew_constrained.yaml",
            iterations=800,
            restarts=3,
            robustness=20,
            seed=0,
        )
    )

    # Write summary JSON
    out = Path("outputs/validation/validation_summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote summary: {out}")

    # Exit code: fail if any case hard-failed (nonzero exit)
    hard_fail = any(c["returncode"] != 0 for c in summary["cases"])
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
