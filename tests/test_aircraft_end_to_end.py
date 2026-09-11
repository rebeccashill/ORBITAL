# tests/test_aircraft_end_to_end.py
"""
Aircraft end-to-end smoke test.

This test is intended to verify the full pipeline for the aircraft module:
YAML -> Problem -> Planner -> Plan -> Simulation -> Constraints -> Objective.

It is a *smoke test*, not a high-fidelity validation.
Once the aircraft module is implemented, this test should pass quickly.

Run:
    pytest -q
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from mission_framework.core.constraints import Severity
from mission_framework.core.planner import Planner, PlannerConfig

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_aircraft_pipeline_runs_end_to_end():
    cfg = _load_yaml(EXAMPLES_DIR / "aircraft_uav_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "aircraft"

    from mission_framework.aircraft.mission import build_problem_from_config

    problem = build_problem_from_config(cfg)

    # Keep runtime small for CI; increase for real runs
    from mission_framework.core.objective import ScoreConfig

    planner_cfg = PlannerConfig(
        iterations=50,
        restarts=1,
        seed=0,
        keep_history=False,
        scoring=ScoreConfig(
            penalty_weight=float(cfg.get("planner", {}).get("penalty_weight", 1000.0)),
        ),
        hard_infeasible_penalty=float(cfg.get("planner", {}).get("hard_infeasible_penalty", 1e6)),
    )

    planner = Planner(planner_cfg)
    result = planner.solve(problem)

    # Basic sanity: returned objects exist
    assert result.assignment is not None
    assert result.plan is not None
    assert result.sim_result is not None
    assert result.constraints is not None
    assert result.score_report is not None

    assert result.plan.kind == "aircraft"
    assert result.constraints.hard_pass is True

    # Constraint report should contain at least one constraint
    assert len(result.constraints.results) > 0
    assert set(result.constraints.by_name()) >= {
        "all_waypoints_reached",
        "bank_angle_turn_limit",
        "battery_nonnegative",
        "geofence_clearance",
        "geofence_no_entry",
    }

    scalars = result.sim_result.scalars
    assert scalars["waypoints_completed"] == scalars["waypoints_total"] == 3.0
    assert scalars["geofence_violated"] == 0.0
    assert scalars["final_battery_Wh"] > 0.0
    assert scalars["energy_used_Wh"] > 0.0
    assert scalars["t_end_s"] > 0.0

    waypoint_ids = [wp["id"] for wp in result.plan.waypoints or []]
    assert waypoint_ids[0] == "START"
    assert set(waypoint_ids[1:]) == {"WP1", "WP2", "WP3"}

    # Check we have sensible objective breakdown
    summary = result.score_report.objective.summary()
    assert "total_cost" in summary
    assert summary["total_cost"] is not None
    assert summary["total_cost"] > 0.0

    # Optional: ensure worst hard margin is finite if hard constraints exist
    worst_hard = result.constraints.worst(Severity.HARD)
    if worst_hard is not None:
        assert worst_hard.min_margin == worst_hard.min_margin  # not NaN


def test_bvlos_powerline_demo_runs_end_to_end(tmp_path: Path):
    cfg = _load_yaml(EXAMPLES_DIR / "bvlos_powerline_inspection_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "aircraft"
    cfg["robustness"]["cases"] = 0

    from mission_framework.aircraft.mission import build_problem_from_config
    from mission_framework.core.objective import ScoreConfig

    problem = build_problem_from_config(cfg)
    assert cfg["weather"]["resolved"]["source"] == "offline Open-Meteo-shaped sample"
    assert cfg["weather"]["resolved"]["timestamp_utc"] == "2026-09-11T16:00:00Z"
    assert cfg["weather"]["applied_to_wind"] is True
    assert cfg["mission"]["geojson_route_loaded"] is True
    assert cfg["geofence"]["geojson_zones_loaded"] == 1

    planner_cfg = PlannerConfig(
        iterations=80,
        restarts=1,
        seed=1,
        keep_history=False,
        scoring=ScoreConfig(
            penalty_weight=float(cfg.get("planner", {}).get("penalty_weight", 1000.0)),
        ),
        hard_infeasible_penalty=float(cfg.get("planner", {}).get("hard_infeasible_penalty", 1e6)),
    )

    result = Planner(planner_cfg).solve(problem)

    assert result.plan.kind == "aircraft"
    assert result.plan.metadata["route_source"].endswith("bvlos_powerline_route.geojson")
    assert result.plan.metadata["geofence_geojson_zones_loaded"] == 1
    assert result.constraints.hard_pass is True
    assert set(result.constraints.by_name()) >= {
        "all_waypoints_reached",
        "battery_nonnegative",
        "battery_reserve",
        "geofence_clearance",
        "geofence_no_entry",
    }

    scalars = result.sim_result.scalars
    assert scalars["waypoints_completed"] == scalars["waypoints_total"] == 6.0
    assert scalars["final_battery_Wh"] >= cfg["vehicle"]["battery_reserve_Wh"]

    waypoint_ids = [wp["id"] for wp in result.plan.waypoints or []]
    assert waypoint_ids == [
        "START",
        "TOWER_01",
        "TOWER_02",
        "TOWER_03",
        "TOWER_04",
        "TOWER_05",
        "TOWER_06",
    ]

    from mission_framework.reporting.flight_output import (
        FLIGHT_PLANNING_EXPORT_NOTICE,
        export_flight_planning_artifacts,
        export_inspection_constraint_audit,
        export_operator_evidence_bundle,
        export_operator_memo,
        export_what_if_plan,
    )

    audit = export_inspection_constraint_audit(
        result.plan,
        result.sim_result,
        result.constraints,
        tmp_path,
        cfg=cfg,
        robustness=result.robustness,
    )

    assert audit["kind"] == "drone_inspection_constraint_audit"
    assert audit["mission_risk"] in {"low", "medium", "high"}
    assert audit["mission_metadata"]["operator"] == "ORBITAL Demo Operations"
    assert audit["mission_metadata"]["aircraft_id"] == "UAV-BVLOS-104"
    assert audit["mission_metadata"]["pilot"] == "Demo Pilot"
    assert audit["mission_metadata"]["organization"] == "Utility Inspection Team"
    assert audit["mission_metadata"]["asset_owner"] == "Palo Alto Grid Demo"
    assert audit["fleet_metadata"]["drone_model"] == "Multirotor inspection UAV"
    assert audit["fleet_metadata"]["battery_pack_id"] == "PACK-900WH-A"
    assert audit["fleet_metadata"]["sensor_payload"] == "RGB + thermal inspection camera"
    assert audit["fleet_metadata"]["inspection_type"] == "Powerline corridor inspection"
    assert audit["regulatory_metadata"]["documentation_only"] is True
    assert audit["regulatory_metadata"]["laanc_required"] is True
    assert audit["regulatory_metadata"]["waiver_or_authorization_required"] is True
    assert audit["regulatory_metadata"]["airspace_class"] == "Class D"
    assert audit["regulatory_metadata"]["visual_observer_required"] is True
    assert audit["weather_metadata"]["source"] == "offline Open-Meteo-shaped sample"
    assert audit["weather_metadata"]["timestamp_utc"] == "2026-09-11T16:00:00Z"
    assert audit["weather_metadata"]["fallback_used"] is True
    assert audit["weather_metadata"]["applied_to_wind"] is True
    assert "ORBITAL does not provide LAANC" in audit["regulatory_metadata"][
        "documentation_only_notice"
    ]
    assert audit["top_limiting_constraint"] is not None
    assert len(audit["top_three_risk_drivers"]) == 3
    assert {check["id"] for check in audit["checks"]} >= {
        "battery_reserve",
        "wind_weather",
        "geofence_clearance",
        "route_completion",
        "turn_bank_feasibility",
    }
    assert (tmp_path / "inspection_constraint_audit.json").exists()
    assert (tmp_path / "inspection_constraint_audit.md").exists()
    memo_text = (tmp_path / "inspection_constraint_audit.md").read_text(encoding="utf-8")
    assert "ORBITAL Demo Operations" in memo_text
    assert "Powerline corridor inspection" in memo_text

    export_operator_memo(
        result.plan,
        result.sim_result,
        result.constraints,
        result.score_report,
        tmp_path / "operator_memo.md",
        robustness=result.robustness,
        cfg=cfg,
    )
    operator_memo = (tmp_path / "operator_memo.md").read_text(encoding="utf-8")
    assert "UAV-BVLOS-104" in operator_memo
    assert "PACK-900WH-A" in operator_memo

    what_if = export_what_if_plan(
        result.plan,
        result.sim_result,
        result.constraints,
        result.score_report,
        tmp_path,
        cfg=cfg,
        robustness=result.robustness,
    )

    assert what_if["kind"] == "drone_inspection_what_if_plan"
    assert {variant["id"] for variant in what_if["variants"]} >= {
        "fewer_waypoints",
        "lower_speed",
        "alternate_launch_point",
        "stronger_wind",
        "larger_battery_reserve",
        "relaunch_battery_swap",
    }
    assert (tmp_path / "what_if_plan.json").exists()
    assert (tmp_path / "what_if_plan.md").exists()

    flight_exports = export_flight_planning_artifacts(result.plan, tmp_path, cfg=cfg)

    assert flight_exports["kind"] == "downstream_flight_planning_exports"
    assert (tmp_path / "autopilot_mission.csv").exists()
    assert (tmp_path / "mission_review.kml").exists()
    assert (tmp_path / "flight_planning_exports.json").exists()
    assert (tmp_path / "flight_planning_exports.md").exists()
    assert FLIGHT_PLANNING_EXPORT_NOTICE in (tmp_path / "autopilot_mission.csv").read_text(
        encoding="utf-8"
    )
    assert FLIGHT_PLANNING_EXPORT_NOTICE in (tmp_path / "mission_review.kml").read_text(
        encoding="utf-8"
    )

    (tmp_path / "plan.json").write_text('{"kind": "aircraft"}\n', encoding="utf-8")
    (tmp_path / "score.json").write_text('{"total_score": 0.0}\n', encoding="utf-8")
    (tmp_path / "flight_path.png").write_bytes(b"png")
    (tmp_path / "robustness.json").write_text('{"cases": 0}\n', encoding="utf-8")
    (tmp_path / "weather.json").write_text(
        '{"source": "offline Open-Meteo-shaped sample"}\n',
        encoding="utf-8",
    )

    evidence = export_operator_evidence_bundle(
        tmp_path,
        EXAMPLES_DIR / "bvlos_powerline_inspection_demo.yaml",
        cfg=cfg,
    )

    assert evidence["kind"] == "operator_evidence_bundle"
    assert evidence["complete"] is True
    assert evidence["weather"]["source"] == "offline Open-Meteo-shaped sample"
    assert evidence["weather"]["timestamp_utc"] == "2026-09-11T16:00:00Z"
    bundle_dir = tmp_path / "operator_evidence_bundle"
    expected_bundle_files = {
        "scenario.yaml",
        "plan.json",
        "inspection_constraint_audit.json",
        "score.json",
        "flight_path.png",
        "robustness.json",
        "operator_memo.md",
        "weather.json",
        "autopilot_mission.csv",
        "mission_review.kml",
        "flight_planning_exports.json",
        "flight_planning_exports.md",
        "manifest.json",
        "README.md",
    }
    assert {path.name for path in bundle_dir.iterdir()} >= expected_bundle_files
