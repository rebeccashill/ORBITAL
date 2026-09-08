from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from run_all import build_cli_cmd

ROOT = Path(__file__).resolve().parents[1]


def test_run_all_builds_supported_no_plots_commands() -> None:
    cmd = build_cli_cmd(
        python=sys.executable,
        yaml_path="examples/aircraft_uav_demo.yaml",
        iterations=5,
        restarts=1,
        robustness=0,
        seed=3,
        extra_args=["--no-plots"],
    )

    assert cmd[:3] == [sys.executable, "-m", "mission_framework.cli"]
    assert "--no-plots" in cmd
    assert cmd[cmd.index("--iterations") + 1] == "5"
    assert cmd[cmd.index("--seed") + 1] == "3"


def test_cli_no_plots_writes_core_artifacts_without_pngs(tmp_path: Path) -> None:
    outdir = tmp_path / "runs"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "examples/aircraft_uav_demo.yaml",
            "--iterations",
            "5",
            "--restarts",
            "1",
            "--robustness",
            "0",
            "--seed",
            "0",
            "--no-plots",
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    scenario_dir = outdir / "aircraft_uav_demo"
    assert (scenario_dir / "score.json").is_file()
    assert (scenario_dir / "constraints.json").is_file()
    assert (scenario_dir / "plan.json").is_file()
    assert (scenario_dir / "waypoints.csv").is_file()
    assert not list(scenario_dir.glob("*.png"))
