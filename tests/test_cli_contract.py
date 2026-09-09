from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import yaml

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


def test_cli_validate_accepts_valid_aircraft_scenario() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "validate",
            "examples/aircraft_uav_demo.yaml",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALID:" in result.stdout
    assert "Scenario: UAV Multi-Waypoint Mission Demo" in result.stdout
    assert "Type: aircraft" in result.stdout
    assert result.stderr == ""


def test_cli_validate_reports_all_errors_for_invalid_scenario(tmp_path: Path) -> None:
    source = ROOT / "examples" / "cubesat_leo_demo.yaml"
    cfg = yaml.safe_load(source.read_text(encoding="utf-8"))
    invalid = copy.deepcopy(cfg)
    invalid["scenario"]["type"] = "spacecraft"
    invalid["orbit"]["time_step_s"] = 0
    invalid["mission"]["targets"][0]["lat_deg"] = 120.0
    invalid["spacecraft"]["initial_battery_Wh"] = 999.0

    scenario_path = tmp_path / "invalid_spacecraft.yaml"
    scenario_path.write_text(yaml.safe_dump(invalid), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "validate",
            str(scenario_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "INVALID:" in result.stderr
    assert "Scenario validation failed" in result.stderr
    assert "orbit.time_step_s" in result.stderr
    assert "mission.targets[0].lat_deg" in result.stderr
    assert "spacecraft.initial_battery_Wh" in result.stderr
