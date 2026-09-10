from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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


def test_cli_seed_reproducibly_writes_same_artifacts(tmp_path: Path) -> None:
    output_roots = [tmp_path / "seed_a", tmp_path / "seed_b"]

    for outdir in output_roots:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mission_framework.cli",
                "examples/aircraft_uav_demo.yaml",
                "--iterations",
                "10",
                "--restarts",
                "1",
                "--robustness",
                "0",
                "--seed",
                "123",
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

    first = output_roots[0] / "aircraft_uav_demo"
    second = output_roots[1] / "aircraft_uav_demo"
    for artifact in ("score.json", "constraints.json", "plan.json", "waypoints.csv"):
        assert (first / artifact).read_bytes() == (second / artifact).read_bytes()


def test_cli_overrides_yaml_settings_and_accepts_single_dash_aliases(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import mission_framework.cli as cli

    captured: dict[str, Any] = {}
    fake_problem = SimpleNamespace(robustness_cases=0)

    def fake_load_yaml(path: Path) -> dict[str, Any]:
        return {
            "scenario": {"name": "Fake Aircraft", "type": "aircraft"},
            "planner": {
                "iterations": 200,
                "restarts": 1,
                "seed": 42,
                "penalty_weight": 2000.0,
            },
            "robustness": {"cases": 20},
            "output": {"save_history": False},
        }

    def fake_build_problem(cfg: dict[str, Any]) -> SimpleNamespace:
        captured["build_cfg"] = copy.deepcopy(cfg)
        return fake_problem

    class FakeConstraints:
        hard_pass = True

        def worst(self, severity: Any) -> None:
            return None

        def to_jsonable(self) -> dict[str, bool]:
            return {"hard_pass": True}

    class FakeScoreReport:
        def to_jsonable(self) -> dict[str, float]:
            return {"total_score": 1.0}

    class FakePlanner:
        def __init__(self, cfg: Any):
            captured["planner_cfg"] = cfg

        def solve(self, problem: Any) -> Any:
            captured["problem"] = problem
            return SimpleNamespace(
                score=1.0,
                constraints=FakeConstraints(),
                score_report=FakeScoreReport(),
                robustness={"cases": problem.robustness_cases},
                plan=SimpleNamespace(kind="fake", metadata={}, waypoints=[]),
                sim_result=SimpleNamespace(),
                history=None,
            )

    written_paths: list[Path] = []

    def fake_write_json(out_path: Path, obj: Any) -> None:
        written_paths.append(out_path)

    monkeypatch.setattr(cli, "_load_yaml", fake_load_yaml)
    monkeypatch.setattr(cli, "validate_scenario_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "_build_problem", fake_build_problem)
    monkeypatch.setattr(cli, "Planner", FakePlanner)
    monkeypatch.setattr(cli, "_write_json", fake_write_json)
    monkeypatch.setattr(cli, "format_feasibility_report", lambda *args, **kwargs: "ok")

    outdir = tmp_path / "custom_runs"
    exit_code = cli.main(
        [
            str(ROOT / "examples" / "aircraft_uav_demo.yaml"),
            "-iterations",
            "7",
            "-restarts",
            "3",
            "-robustness",
            "4",
            "-seed",
            "99",
            "-outdir",
            str(outdir),
            "-no-plots",
        ]
    )

    assert exit_code == 0
    build_cfg = captured["build_cfg"]
    planner_cfg = captured["planner_cfg"]
    assert build_cfg["planner"]["iterations"] == 7
    assert build_cfg["planner"]["restarts"] == 3
    assert build_cfg["planner"]["seed"] == 99
    assert build_cfg["robustness"]["cases"] == 4
    assert planner_cfg.iterations == 7
    assert planner_cfg.restarts == 3
    assert planner_cfg.seed == 99
    assert captured["problem"].robustness_cases == 4

    scenario_dir = outdir.resolve() / "aircraft_uav_demo"
    assert written_paths
    assert all(path.parent == scenario_dir for path in written_paths)


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
