from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from mission_framework.scenario_validation import (
    AIRCRAFT_SCHEMA,
    SHARED_SCENARIO_FIELDS,
    SPACECRAFT_SCHEMA,
    ScenarioValidationError,
    collect_scenario_validation_issues,
    validate_scenario_config,
)
from scripts.run_validation import VALIDATION_CASES

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _issue_paths(issues) -> set[str]:
    return {issue.path for issue in issues}


def test_schema_definitions_cover_shared_and_domain_fields() -> None:
    assert SHARED_SCENARIO_FIELDS == (
        "scenario.name",
        "scenario.type",
        "planner",
        "output",
        "robustness",
    )
    assert AIRCRAFT_SCHEMA.scenario_type == "aircraft"
    assert "mission.waypoints[]" in AIRCRAFT_SCHEMA.required_fields
    assert SPACECRAFT_SCHEMA.scenario_type == "spacecraft"
    assert "mission.targets[]" in SPACECRAFT_SCHEMA.required_fields


@pytest.mark.parametrize(
    "scenario_path",
    [
        EXAMPLES / "aircraft_uav_demo.yaml",
        EXAMPLES / "cubesat_leo_demo.yaml",
        EXAMPLES / "stress" / "aircraft_high_wind.yaml",
        EXAMPLES / "stress" / "aircraft_low_battery_tight_nfzs.yaml",
        EXAMPLES / "stress" / "spacecraft_power_starved.yaml",
        EXAMPLES / "stress" / "spacecraft_slew-constrained.yaml",
    ],
)
def test_bundled_scenarios_validate(scenario_path: Path) -> None:
    cfg = _load_yaml(scenario_path)
    assert collect_scenario_validation_issues(cfg) == []


def test_validation_script_stress_inventory_matches_examples() -> None:
    stress_files = {path.resolve() for path in (EXAMPLES / "stress").glob("*.yaml")}
    inventory_files = {
        (ROOT / str(case["yaml_path"])).resolve()
        for case in VALIDATION_CASES
        if str(case["yaml_path"]).startswith("examples/stress/")
    }

    assert inventory_files == stress_files


def test_aircraft_validation_reports_actionable_errors() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    del cfg["mission"]["waypoints"][0]["x_m"]
    cfg["vehicle"]["cruise_speed_mps"] = 100.0
    cfg["geofence"]["no_fly_zones"][0]["polygon"] = [[0.0, 0.0], [1.0, 1.0]]
    cfg["output"]["verbose"] = "yes"
    cfg["objective"]["terms"][0]["mode"] = "lower"
    cfg["robustness"]["wind_scale_range"] = [1.2, 0.8]

    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)

    assert "mission.waypoints[0].x_m" in paths
    assert "vehicle.cruise_speed_mps" in paths
    assert "geofence.no_fly_zones[0].polygon" in paths
    assert "output.verbose" in paths
    assert "objective.terms[0].mode" in paths
    assert "robustness.wind_scale_range" in paths

    with pytest.raises(ScenarioValidationError) as exc_info:
        validate_scenario_config(cfg)

    message = str(exc_info.value)
    assert "Scenario validation failed" in message
    assert "mission.waypoints[0].x_m" in message


def test_spacecraft_validation_reports_actionable_errors() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "cubesat_leo_demo.yaml"))
    cfg["orbit"]["time_step_s"] = 0
    cfg["mission"]["targets"][0]["lat_deg"] = 120.0
    cfg["mission"]["targets"][0]["time_windows"][0]["end_utc"] = "2025-12-31T00:00:00Z"
    cfg["ground_stations"][0]["min_elevation_deg"] = 95.0
    cfg["spacecraft"]["initial_battery_Wh"] = 999.0
    cfg["spacecraft"]["data_rate_downlink_Mbps"] = 0.0

    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)

    assert "orbit.time_step_s" in paths
    assert "mission.targets[0].lat_deg" in paths
    assert "mission.targets[0].time_windows[0].end_utc" in paths
    assert "ground_stations[0].min_elevation_deg" in paths
    assert "spacecraft.initial_battery_Wh" in paths
    assert "spacecraft.data_rate_downlink_Mbps" in paths


def test_unknown_scenario_type_gets_clear_error() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["scenario"]["type"] = "balloon"

    with pytest.raises(ScenarioValidationError, match="Use 'aircraft' or 'spacecraft'"):
        validate_scenario_config(cfg)


def test_builders_validate_before_constructing_problem() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    del cfg["mission"]["waypoints"][0]["x_m"]

    from mission_framework.aircraft.mission import build_problem_from_config

    with pytest.raises(ScenarioValidationError, match="mission.waypoints\\[0\\].x_m"):
        build_problem_from_config(cfg)


def test_cli_prints_validation_errors_without_running_planner(tmp_path: Path) -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["planner"]["iterations"] = 0
    del cfg["mission"]["waypoints"][0]["x_m"]

    invalid_path = tmp_path / "invalid_aircraft.yaml"
    invalid_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "mission_framework.cli", str(invalid_path), "--no-plots"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "Scenario validation failed" in result.stderr
    assert "planner.iterations" in result.stderr
    assert "mission.waypoints[0].x_m" in result.stderr
