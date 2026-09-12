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


def _error_issues(issues):
    return [issue for issue in issues if issue.is_error]


def _warning_issues(issues):
    return [issue for issue in issues if issue.is_warning]


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
        EXAMPLES / "bvlos_powerline_inspection_demo.yaml",
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


def test_aircraft_validation_allows_named_output_folder() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["vehicle"]["battery_reserve_Wh"] = 100.0
    cfg["output"]["run_dir_name"] = "bvlos_powerline_inspection"

    assert collect_scenario_validation_issues(cfg) == []

    cfg["output"]["run_dir_name"] = "../unsafe"
    issues = collect_scenario_validation_issues(cfg)
    assert "output.run_dir_name" in _issue_paths(issues)


def test_evidence_bundle_review_metadata_is_optional_and_validated() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["vehicle"]["battery_reserve_Wh"] = 100.0
    cfg["evidence_bundle"] = {
        "operator_review_status": "ready_for_review",
        "reviewer_name": "Demo reviewer",
        "review_timestamp_utc": "2026-09-11T19:00:00Z",
    }

    assert collect_scenario_validation_issues(cfg) == []

    cfg["evidence_bundle"]["operator_review_status"] = "approved"
    cfg["evidence_bundle"]["reviewer_name"] = ""
    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)
    assert "evidence_bundle.operator_review_status" in paths
    assert "evidence_bundle.reviewer_name" in paths


def test_aircraft_regulatory_metadata_validates_as_documentation_fields() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["regulatory"] = {
        "laanc_required": True,
        "waiver_or_authorization_required": False,
        "airspace_class": "Class G",
        "visual_observer_required": True,
        "ground_risk_population_note": "Sparse rural corridor.",
        "authorization_id": "sample authorization reference",
        "approving_authority_source": "Example authority source record",
        "authorization_expiration_date": "2026-09-11",
        "operating_altitude_limit_m": 120.0,
        "operating_time_window": {
            "start_utc": "2026-09-11T16:00:00Z",
            "end_utc": "2026-09-11T18:00:00Z",
        },
        "required_crew_roles": ["Remote pilot in command", "Visual observer"],
        "special_conditions_limitations": ["Remain below authorized altitude."],
        "operating_assumptions": ["Pilot-in-command verifies local requirements."],
        "unresolved_items": ["Confirm final site access approval."],
        "documentation_only_notice": "Documentation only; not legal approval.",
    }

    assert collect_scenario_validation_issues(cfg) == []

    cfg["regulatory"]["laanc_required"] = "yes"
    cfg["regulatory"]["airspace_class"] = ""
    cfg["regulatory"]["authorization_id"] = ""
    cfg["regulatory"]["operating_altitude_limit_m"] = -1
    cfg["regulatory"]["operating_time_window"]["start_utc"] = ""
    cfg["regulatory"]["required_crew_roles"] = [""]
    cfg["regulatory"]["special_conditions_limitations"] = "none"
    cfg["regulatory"]["operating_assumptions"] = ["  "]
    cfg["regulatory"]["unresolved_items"] = "Confirm waiver"
    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)
    assert "regulatory.laanc_required" in paths
    assert "regulatory.airspace_class" in paths
    assert "regulatory.authorization_id" in paths
    assert "regulatory.operating_altitude_limit_m" in paths
    assert "regulatory.operating_time_window.start_utc" in paths
    assert "regulatory.required_crew_roles[0]" in paths
    assert "regulatory.special_conditions_limitations" in paths
    assert "regulatory.operating_assumptions[0]" in paths
    assert "regulatory.unresolved_items" in paths


def test_bvlos_regulatory_documentation_warnings_do_not_block_planning() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "bvlos_powerline_inspection_demo.yaml"))
    del cfg["regulatory"]["authorization_id"]
    del cfg["regulatory"]["airspace_class"]
    cfg["regulatory"]["required_crew_roles"] = ["Remote pilot in command"]

    issues = collect_scenario_validation_issues(cfg)
    warnings = _warning_issues(issues)

    assert _error_issues(issues) == []
    assert {warning.path for warning in warnings} >= {
        "regulatory",
        "regulatory.authorization_id",
        "regulatory.required_crew_roles",
    }
    warning_text = "\n".join(warning.message for warning in warnings)
    assert "BVLOS regulatory metadata is incomplete" in warning_text
    assert "LAANC is required but no authorization reference is supplied" in warning_text
    assert "waiver / authorization is required but no reference is supplied" in warning_text
    assert "visual observer is required but no visual observer crew role is documented" in (
        warning_text
    )

    assert validate_scenario_config(cfg)["scenario"]["type"] == "aircraft"


def test_aircraft_weather_metadata_validates_provider_fields() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["weather"] = {
        "enabled": True,
        "provider": "open_meteo",
        "use_live": False,
        "fallback_enabled": True,
        "apply_to_wind": True,
        "timestamp_utc": "2026-09-11T16:00:00Z",
        "timeout_s": 6.0,
        "location": {
            "name": "Demo corridor",
            "latitude_deg": 37.4419,
            "longitude_deg": -122.1430,
        },
        "forecast_window": {
            "start_utc": "2026-09-11T16:00:00Z",
            "hours": 2.0,
        },
        "offline": {
            "source": "offline sample",
            "timestamp_utc": "2026-09-11T16:00:00Z",
            "wind_speed_mps": 4.5,
            "wind_direction_deg": 285.0,
            "wind_gust_mps": 5.9,
            "visibility_m": 16000.0,
            "precipitation_mm": 0.0,
            "temperature_C": 18.5,
        },
        "operational_limits": {
            "max_safe_wind_mps": 9.0,
            "warning_margin_mps": 2.0,
        },
    }

    assert collect_scenario_validation_issues(cfg) == []

    cfg["weather"]["provider"] = "unknown"
    cfg["weather"]["location"]["latitude_deg"] = 100.0
    cfg["weather"]["offline"]["wind_direction_deg"] = 400.0
    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)
    assert "weather.provider" in paths
    assert "weather.location.latitude_deg" in paths
    assert "weather.offline.wind_direction_deg" in paths


def test_aircraft_mission_and_fleet_metadata_are_optional_documentation() -> None:
    cfg = copy.deepcopy(_load_yaml(EXAMPLES / "aircraft_uav_demo.yaml"))
    cfg["mission_metadata"] = {
        "operator": "Demo Operator",
        "aircraft_id": "UAV-001",
        "pilot": "Demo Pilot",
        "organization": "Inspection Team",
        "asset_owner": "Utility Owner",
    }
    cfg["fleet_metadata"] = {
        "drone_model": "Inspection UAV",
        "battery_pack_id": "BAT-001",
        "sensor_payload": "RGB camera",
        "inspection_type": "Powerline inspection",
    }

    assert collect_scenario_validation_issues(cfg) == []

    cfg["mission_metadata"]["operator"] = ""
    cfg["fleet_metadata"]["drone_model"] = ""
    issues = collect_scenario_validation_issues(cfg)
    paths = _issue_paths(issues)
    assert "mission_metadata.operator" in paths
    assert "fleet_metadata.drone_model" in paths
