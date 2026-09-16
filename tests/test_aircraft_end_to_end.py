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

import copy
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


def test_bvlos_powerline_demo_runs_end_to_end(tmp_path: Path, monkeypatch):
    cfg = _load_yaml(EXAMPLES_DIR / "bvlos_powerline_inspection_demo.yaml")
    assert cfg["scenario"]["type"].lower() == "aircraft"
    cfg["robustness"]["cases"] = 0
    cfg["weather"]["provider"] = "mock"
    cfg["weather"]["use_live"] = False

    from mission_framework.aircraft.mission import build_problem_from_config
    from mission_framework.core.objective import ScoreConfig

    problem = build_problem_from_config(cfg)
    assert cfg["weather"]["resolved"]["provider"] == "mock"
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
        export_regulatory_readiness_report,
        export_what_if_plan,
        verify_evidence_bundle_checksums,
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
    assert audit["primary_demo_artifact"] is True
    assert audit["operator_question"] == "Can we safely and defensibly fly this mission?"
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
    assert audit["weather_metadata"]["fallback_used"] is False
    assert audit["weather_metadata"]["applied_to_wind"] is True
    assert (
        "ORBITAL does not provide LAANC"
        in audit["regulatory_metadata"]["documentation_only_notice"]
    )
    assert audit["top_limiting_constraint"] is not None
    assert audit["top_limiting_constraint_selection"]["selected_constraint_id"] == (
        audit["top_limiting_constraint"]["id"]
    )
    assert "highest risk_points" in audit["top_limiting_constraint_selection"]["explanation"]
    transparency = audit["model_transparency"]
    assumption_ids = {item["id"] for item in transparency["assumptions_report"]}
    assert {
        "battery",
        "wind",
        "geofence",
        "route_completion",
        "turn_feasibility",
        "robustness",
    } <= assumption_ids
    assert transparency["reproducibility"]["scenario_path"] == "not provided"
    assert transparency["reproducibility"]["command"]["display"] == "not provided"
    assert {item["id"] for item in transparency["model_limitations"]} >= {
        "offline_sample_weather",
        "simplified_flight_dynamics",
    }
    assert len(audit["top_three_risk_drivers"]) == 3
    assert len(audit["constraint_groups"]) == 5
    assert {check["id"] for check in audit["checks"]} >= {
        "battery_reserve",
        "wind_weather",
        "geofence_clearance",
        "route_completion",
        "turn_bank_feasibility",
    }
    for group in audit["constraint_groups"]:
        assert group["status"] in {"pass", "warning", "fail", "unknown"}
        assert group["plain_english"]
        assert group["why_this_matters_to_operator"]
        assert group["recommended_operator_action"]
        assert group["status_meaning"]
        assert group["margin"]["unit"]
        assert group["margin"]["source"]
        assert group["warning_margin"]["source"]
    assert (tmp_path / "inspection_constraint_audit.json").exists()
    assert (tmp_path / "inspection_constraint_audit.md").exists()
    memo_text = (tmp_path / "inspection_constraint_audit.md").read_text(encoding="utf-8")
    assert "Primary demo artifact" in memo_text
    assert "Can we safely and defensibly fly this mission?" in memo_text
    assert "Selection detail" in memo_text
    assert "Model Transparency" in memo_text
    assert "Assumptions Report" in memo_text
    assert "Constraint Margin Units And Sources" in memo_text
    assert "Reproducibility" in memo_text
    assert "Model Limitations" in memo_text
    assert "Constraint Group Summary" in memo_text
    assert "Why this matters to an operator" in memo_text
    assert "Recommended operator action" in memo_text
    assert "ORBITAL Demo Operations" in memo_text
    assert "Powerline corridor inspection" in memo_text

    regulatory_report = export_regulatory_readiness_report(
        result.plan,
        result.sim_result,
        result.constraints,
        tmp_path,
        cfg=cfg,
        robustness=result.robustness,
    )

    assert regulatory_report["kind"] == "regulatory_readiness_report"
    assert regulatory_report["status"] == "operator_action_required"
    assert regulatory_report["decision_support_only"] is True
    assert regulatory_report["not_legal_approval"] is True
    assert "decision support only and is not legal approval" in regulatory_report["disclaimer"]
    assert regulatory_report["regulatory_summary"]["laanc_required"]["status"] == "required"
    assert (
        regulatory_report["regulatory_summary"]["waiver_or_authorization_required"]["status"]
        == "required"
    )
    assert regulatory_report["regulatory_summary"]["airspace_class"]["configured"] == "Class D"
    assert regulatory_report["regulatory_summary"]["visual_observer_required"]["status"] == (
        "required"
    )
    assert (
        "Utility corridor inspection"
        in regulatory_report["regulatory_summary"]["ground_risk_population_note"]["summary"]
    )
    evidence = regulatory_report["regulatory_evidence"]
    assert evidence["documentation_only"] is True
    assert evidence["authorization_id"] == "example authorization reference only"
    assert (
        evidence["approving_authority_source"]
        == "Operator-provided example authority source for documentation-only demo"
    )
    assert evidence["authorization_expiration_date"] == "2026-12-31"
    assert evidence["operating_altitude_limit_m"] == 120.0
    assert evidence["operating_time_window"] == {
        "start_utc": "2026-09-11T16:00:00Z",
        "end_utc": "2026-09-11T18:00:00Z",
    }
    assert evidence["required_crew_roles"] == [
        "Remote pilot in command",
        "Visual observer",
    ]
    assert "modeled utility corridor" in evidence["special_conditions_limitations"][0]
    assert "lost-link" in evidence["emergency_contingency_plan"]
    assert "does not verify" in evidence["notice"]
    assert regulatory_report["operating_assumptions"]
    unresolved_ids = {item["id"] for item in regulatory_report["unresolved_regulatory_items"]}
    assert "laanc_authorization_confirmation" in unresolved_ids
    assert "waiver_or_authorization_confirmation" in unresolved_ids
    assert "visual_observer_staffing_plan" in unresolved_ids
    checklist = regulatory_report["operator_approval_checklist"]
    checklist_ids = {item["id"] for item in checklist}
    assert checklist_ids >= {
        "laanc_confirmation",
        "waiver_authorization_confirmation",
        "visual_observer_assignment",
        "crew_briefing",
        "emergency_contingency_plan",
        "notam_local_restriction_review",
        "weather_minimums_confirmation",
        "battery_reserve_confirmation",
    }
    assert all(item["checked"] is False for item in checklist)
    assert all(item["status"] == "operator_confirmation_required" for item in checklist)
    assert (tmp_path / "regulatory_readiness_report.json").exists()
    assert (tmp_path / "regulatory_readiness_report.md").exists()
    regulatory_md = (tmp_path / "regulatory_readiness_report.md").read_text(encoding="utf-8")
    assert "Regulatory Readiness Report" in regulatory_md
    assert "Regulatory Evidence Fields" in regulatory_md
    assert "example authorization reference only" in regulatory_md
    assert "Operating altitude limit: 120.0 m" in regulatory_md
    assert "Remote pilot in command, Visual observer" in regulatory_md
    assert "Operator Approval Checklist" in regulatory_md
    assert "- [ ] Confirm crew briefing completed" in regulatory_md
    assert "- [ ] Confirm emergency / contingency plan" in regulatory_md
    assert "- [ ] Confirm NOTAM / local restriction review" in regulatory_md
    assert "- [ ] Confirm weather minimums" in regulatory_md
    assert "- [ ] Confirm battery reserve" in regulatory_md
    assert "not legal approval" in regulatory_md.lower()

    no_conditional_cfg = copy.deepcopy(cfg)
    no_conditional_cfg["regulatory"]["laanc_required"] = False
    no_conditional_cfg["regulatory"]["waiver_or_authorization_required"] = False
    no_conditional_cfg["regulatory"]["visual_observer_required"] = False
    no_conditional_report = export_regulatory_readiness_report(
        result.plan,
        result.sim_result,
        result.constraints,
        tmp_path / "no_conditional_regulatory",
        cfg=no_conditional_cfg,
        robustness=result.robustness,
    )
    no_conditional_ids = {
        item["id"] for item in no_conditional_report["operator_approval_checklist"]
    }
    assert "laanc_confirmation" not in no_conditional_ids
    assert "waiver_authorization_confirmation" not in no_conditional_ids
    assert "visual_observer_assignment" not in no_conditional_ids
    assert no_conditional_ids >= {
        "crew_briefing",
        "emergency_contingency_plan",
        "notam_local_restriction_review",
        "weather_minimums_confirmation",
        "battery_reserve_confirmation",
    }

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
    assert what_if["before_after_improvements"]
    assert {item["variant_id"] for item in what_if["before_after_improvements"]} & {
        "fewer_waypoints",
        "lower_speed",
        "relaunch_battery_swap",
    }
    assert (tmp_path / "what_if_plan.json").exists()
    assert (tmp_path / "what_if_plan.md").exists()
    what_if_md = (tmp_path / "what_if_plan.md").read_text(encoding="utf-8")
    assert "Before / After Improvements" in what_if_md
    assert "| Scenario | What changed | Risk | Feasible |" in what_if_md
    assert "Changed time" in what_if_md
    assert "Battery reserve margin" in what_if_md

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
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        relative_exports = export_flight_planning_artifacts(
            result.plan,
            tmp_path / "repo_relative_exports",
            cfg=cfg,
        )
    assert relative_exports["artifacts"]["autopilot_mission_csv"]["path"] == (
        "repo_relative_exports/autopilot_mission.csv"
    )
    assert relative_exports["artifacts"]["mission_review_kml"]["path"] == (
        "repo_relative_exports/mission_review.kml"
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
        generated_timestamp_utc="2026-09-15T05:24:50Z",
    )

    assert evidence["kind"] == "operator_evidence_bundle"
    assert evidence["complete"] is True
    assert evidence["bundle_completeness_score"] == 100.0
    assert evidence["bundle_completeness"]["complete"] is True
    assert evidence["manifest_version"] == 1
    assert evidence["ui_manifest_version"] == 1
    assert evidence["scenario_path"] == "examples/bvlos_powerline_inspection_demo.yaml"
    assert evidence["freshness"]["scenario_path"] == evidence["scenario_path"]
    assert Path(evidence["scenario_path"]).is_absolute() is False
    assert evidence["ui_compatibility"]["schema_version"] == 1
    assert "manifest_version" in evidence["ui_compatibility"]["required_top_level_fields"]
    assert evidence["ui_compatibility"]["artifact_access"]["outside_ui_required"] is True
    assert "dashboard" in evidence["ui_compatibility"]["artifact_access"]["expected_formats"]
    assert (
        evidence["ui_compatibility"]["artifact_access"]["primary_dashboard"]
        == "operator_dashboard.md"
    )
    assert (
        evidence["ui_compatibility"]["artifact_access"]["visual_review_ui"]
        == "operator_review_ui.html"
    )
    assert (
        "non-link unavailable labels"
        in evidence["ui_compatibility"]["artifact_access"]["unavailable_artifact_policy"]
    )
    assert evidence["artifact_completeness"]["score"] == 100.0
    assert evidence["regulatory_documentation_completeness"]["score"] == 100.0
    assert evidence["regulatory_documentation_completeness"]["documented_fields"] == 11
    assert evidence["regulatory_documentation_completeness"]["total_fields"] == 11
    assert {warning["kind"] for warning in evidence["bundle_warnings"]} >= {
        "weather_evidence",
        "regulatory_evidence_provenance",
    }
    assert evidence["missing_evidence"] == []
    assert evidence["operator_review"]["status"] == "ready_for_review"
    assert evidence["operator_review"]["reviewer_name"] is None
    assert evidence["operator_review"]["review_timestamp_utc"] is None
    assert (
        evidence["operator_review"]["review_notes"]
        == "Demo bundle ready for operator review; final approval remains outside ORBITAL."
    )
    assert evidence["operator_review"]["operator_decision"] == "pending operator review"
    assert evidence["review_metadata"]["schema_version"] == 1
    assert evidence["review_metadata"]["status"] == "ready_for_review"
    assert evidence["review_metadata"]["operator_decision"] == "pending operator review"
    assert evidence["freshness"]["generated_timestamp_utc"] == "2026-09-15T05:24:50Z"
    assert evidence["freshness"]["orbital_version"] != "unknown"
    assert evidence["freshness"]["scenario_hash"]["algorithm"] == "sha256"
    assert len(evidence["freshness"]["scenario_hash"]["value"]) == 64
    assert evidence["freshness"]["command"]["display"] == "not provided"
    assert evidence["weather"]["source"] == "offline Open-Meteo-shaped sample"
    assert evidence["weather"]["timestamp_utc"] == "2026-09-11T16:00:00Z"
    assert evidence["weather_evidence_readiness"]["status"] == "STALE"
    assert evidence["weather_evidence_readiness"]["mode"] == "sample"
    assert evidence["regulatory_evidence_provenance"]["status"] == "STALE"
    assert (
        evidence["regulatory_evidence_provenance"]["operator_confirmation_status"]
        == "pending_operator_confirmation"
    )
    assert evidence["checksum_evidence_readiness"]["status"] == "VERIFY REQUIRED"
    plan_freshness = next(
        artifact["freshness"] for artifact in evidence["artifacts"] if artifact["id"] == "plan_json"
    )
    assert plan_freshness["source_modified_utc"] == "2026-09-15T05:24:50Z"
    assert plan_freshness["bundle_modified_utc"] == "2026-09-15T05:24:50Z"
    assert evidence["regulatory_metadata"]["laanc_required"] is True
    assert evidence["regulatory_metadata"]["waiver_or_authorization_required"] is True
    assert evidence["regulatory_metadata"]["airspace_class"] == "Class D"
    assert (
        evidence["regulatory_evidence"]["authorization_id"]
        == "example authorization reference only"
    )
    assert "lost-link" in evidence["regulatory_metadata"]["emergency_contingency_plan"]
    assert "lost-link" in evidence["regulatory_evidence"]["emergency_contingency_plan"]
    assert evidence["regulatory_evidence_status"]["missing"] == []
    assert evidence["regulatory_evidence_status"]["all_optional_fields_documented"] is True
    assert evidence["approval_checklist"]["source_artifact"] == "regulatory_readiness_report.json"
    assert evidence["approval_checklist"]["item_count"] == len(checklist)
    for artifact in evidence["artifacts"]:
        assert "freshness" in artifact
        assert artifact["opens_outside_ui"] is True
        assert artifact["ui_link_behavior"] == "link_when_present_else_unavailable_label"
        assert artifact["artifact_format"]
        if artifact["present"]:
            assert artifact["freshness"]["bundle_sha256"]
            assert artifact["freshness"]["stale_against_scenario"] is False
    manifest_checklist_ids = {item["id"] for item in evidence["approval_checklist"]["items"]}
    assert manifest_checklist_ids >= {
        "laanc_confirmation",
        "waiver_authorization_confirmation",
        "visual_observer_assignment",
        "crew_briefing",
        "emergency_contingency_plan",
        "notam_local_restriction_review",
        "weather_minimums_confirmation",
        "battery_reserve_confirmation",
    }
    bundle_dir = tmp_path / "operator_evidence_bundle"
    expected_bundle_files = {
        "scenario.yaml",
        "plan.json",
        "inspection_constraint_audit.md",
        "inspection_constraint_audit.json",
        "regulatory_readiness_report.json",
        "regulatory_readiness_report.md",
        "what_if_plan.md",
        "what_if_plan.json",
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
        "operator_review_ui.html",
        "operator_dashboard.md",
        "evidence_bundle_summary.md",
        "artifact_index.md",
        "checksum_manifest.json",
    }
    assert {path.name for path in bundle_dir.iterdir()} >= expected_bundle_files
    bundle_readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
    operator_review_ui = (bundle_dir / "operator_review_ui.html").read_text(encoding="utf-8")
    operator_dashboard = (bundle_dir / "operator_dashboard.md").read_text(encoding="utf-8")
    bundle_summary = (bundle_dir / "evidence_bundle_summary.md").read_text(encoding="utf-8")
    artifact_index = (bundle_dir / "artifact_index.md").read_text(encoding="utf-8")
    assert "Start with `operator_dashboard.md`" in bundle_readme
    assert "operator_review_ui.html" in bundle_readme
    assert "local read-only browser view" in bundle_readme
    assert "## Open This First" in bundle_readme
    assert "## How To Review This Bundle" in bundle_readme
    assert "## How To Archive This Bundle" in bundle_readme
    assert "## Completeness And Verification" in bundle_readme
    assert "Regulatory documentation completeness is reported separately" in bundle_readme
    assert "bundle-verify" in bundle_readme
    assert "Regulatory Readiness" in bundle_readme
    assert "Weather / Live Evidence Readiness" in bundle_readme
    assert "Regulatory Evidence Provenance" in bundle_readme
    assert "Approval Checklist" in bundle_readme
    assert "documentation-only" in bundle_readme
    assert "not proof of authorization" in bundle_readme
    assert "ORBITAL Operator Review UI" in operator_review_ui
    assert "Mission Verdict:" in operator_review_ui
    assert "REVIEW REQUIRED" in operator_review_ui
    assert "Next operator action" in operator_review_ui
    assert "Review Order" in operator_review_ui
    assert (
        "Verdict -> top constraint -> trust signals -> artifacts -> checksum" in operator_review_ui
    )
    assert "First artifact to open" in operator_review_ui
    assert "Raw Evidence Quick Links" in operator_review_ui
    assert "Manifest Compatibility" in operator_review_ui
    assert "Manifest version" in operator_review_ui
    assert "UI schema" in operator_review_ui
    assert "Markdown, JSON, CSV, KML, PNG, manifest, checksum, dashboard" in operator_review_ui
    assert "Checksum Review" in operator_review_ui
    assert "Print / demo view" in operator_review_ui
    assert 'class="skip-link"' in operator_review_ui
    assert 'tabindex="0"' in operator_review_ui
    assert "Why This Verdict?" in operator_review_ui
    assert "Model Assumptions" in operator_review_ui
    assert "Artifact Freshness" in operator_review_ui
    assert "Operator should verify" in operator_review_ui
    assert "Modeled mission status" in operator_review_ui
    assert "Mission risk" in operator_review_ui
    assert "Top limiting constraint" in operator_review_ui
    assert "Regulatory readiness" in operator_review_ui
    assert "Evidence Completeness" in operator_review_ui
    assert "Documentation" in operator_review_ui
    assert "Weather evidence" in operator_review_ui
    assert "Weather / Live Evidence" in operator_review_ui
    assert "Robustness" in operator_review_ui
    assert "Missing evidence" in operator_review_ui
    assert "Warning total" in operator_review_ui
    assert "local review surface" in operator_review_ui
    assert "decision support, not approval" in operator_review_ui
    assert "does not approve a mission" in operator_review_ui
    assert "documentation-only records" in operator_review_ui
    assert "flight_path.png" in operator_review_ui
    assert "operator_dashboard.md" in operator_review_ui
    assert "manifest.json" in operator_review_ui
    assert "ORBITAL Operator Evidence Dashboard" in operator_dashboard
    assert "Mission Verdict: REVIEW REQUIRED" in operator_dashboard
    assert "30-Second Review Path" in operator_dashboard
    assert (
        "Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum."
        in operator_dashboard
    )
    assert (
        "**First artifact to open:** [operator_dashboard.md](operator_dashboard.md)"
        in operator_dashboard
    )
    assert "Raw Evidence Quick Links" in operator_dashboard
    assert "Manifest Compatibility" in operator_dashboard
    assert "| Manifest version | 1 |" in operator_dashboard
    assert (
        "Unavailable artifacts are rendered as unavailable text, not links." in operator_dashboard
    )
    assert "| Raw Markdown |" in operator_dashboard
    assert "| JSON Evidence |" in operator_dashboard
    assert "| CSV / KML |" in operator_dashboard
    assert "| Plots |" in operator_dashboard
    assert "| Manifest / checksum |" in operator_dashboard
    assert "Mission Card" in operator_dashboard
    assert "Why This Verdict?" in operator_dashboard
    assert "The verdict is REVIEW REQUIRED because modeled feasibility is GO" in operator_dashboard
    assert "Model Assumptions Snapshot" in operator_dashboard
    assert "| Verdict | REVIEW REQUIRED |" in operator_dashboard
    assert "10-Second Mission Read" in operator_dashboard
    assert "Recommended Opening Sequence" in operator_dashboard
    assert "| Signal | Current value | Operator cue |" in operator_dashboard
    assert "Mission status: GO" in operator_dashboard
    assert "Mission risk: LOW" in operator_dashboard
    assert "Top limiting constraint:" in operator_dashboard
    assert "Regulatory readiness: OPERATOR_ACTION_REQUIRED" in operator_dashboard
    assert "Bundle completeness: 100.0 %" in operator_dashboard
    assert "Weather evidence status" in operator_dashboard
    assert "Regulatory provenance" in operator_dashboard
    assert "Checksum evidence" in operator_dashboard
    assert "Robustness status" in operator_dashboard
    assert "No robustness cases were recorded" in operator_dashboard
    assert "Trust And Defensibility" in operator_dashboard
    assert "Sample Data / Demo Scenario Note" in operator_dashboard
    assert "Model Assumptions Summary" in operator_dashboard
    assert "Known Limitations Summary" in operator_dashboard
    assert "Evidence Warnings At A Glance" in operator_dashboard
    assert "Stale / Missing / Mismatched Evidence Scan" in operator_dashboard
    assert "Artifact Freshness Summary" in operator_dashboard
    assert "Operator decision: pending operator review" in operator_dashboard
    assert "Review notes: Demo bundle ready for operator review" in operator_dashboard
    assert "not approval, not authorization, not legal advice" in operator_dashboard
    assert "Feasibility And Decision Support" in operator_dashboard
    assert "Route, Export, And Field-Use Artifacts" in operator_dashboard
    assert "[what_if_plan.md](what_if_plan.md)" in operator_dashboard
    assert "[manifest.json](manifest.json)" in operator_dashboard
    assert "[checksum_manifest.json](checksum_manifest.json)" in operator_dashboard
    assert "[flight_path.png](flight_path.png)" in operator_dashboard
    assert "[autopilot_mission.csv](autopilot_mission.csv)" in operator_dashboard
    assert "[mission_review.kml](mission_review.kml)" in operator_dashboard
    assert "Completeness score: 100.0 %" in bundle_summary
    assert "UI Manifest Compatibility" in bundle_summary
    assert "Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts" in (
        bundle_summary
    )
    assert "Reviewer Snapshot" in bundle_summary
    assert "Recommended Review Flow" in bundle_summary
    assert "Artifact completeness score: 100.0 %" in bundle_summary
    assert "Regulatory documentation completeness score: 100.0 %" in bundle_summary
    assert "Generated timestamp UTC:" in bundle_summary
    assert "Scenario SHA-256:" in bundle_summary
    assert "Command used: not provided" in bundle_summary
    assert "Bundle Warnings" in bundle_summary
    assert "Trust And Defensibility" in bundle_summary
    assert "Weather evidence readiness:" in bundle_summary
    assert "Regulatory evidence provenance:" in bundle_summary
    assert "Checksum evidence readiness:" in bundle_summary
    assert "Uncertainty / robustness status:" in bundle_summary
    assert "Operator review status: ready for review" in bundle_summary
    assert "Operator decision: pending operator review" in bundle_summary
    assert "Review notes: Demo bundle ready for operator review" in bundle_summary
    assert "Missing Evidence" in bundle_summary
    assert "Open First" in artifact_index
    assert "Review Path" in artifact_index
    assert "Artifact Status Summary" in artifact_index
    assert "Recommended Opening Order" in artifact_index
    assert "[inspection_constraint_audit.md](inspection_constraint_audit.md)" in artifact_index
    assert "[operator_dashboard.md](operator_dashboard.md)" in artifact_index
    assert "[what_if_plan.md](what_if_plan.md)" in artifact_index
    bundle_manifest = _load_yaml(bundle_dir / "manifest.json")
    assert bundle_manifest["trust_defensibility"]["weather_fallback_status"]["status"]
    assert (
        bundle_manifest["trust_defensibility"]["uncertainty_robustness_status"]["status"]
        == "NOT RUN"
    )
    assert bundle_manifest["trust_defensibility"]["uncertainty_robustness_status"]["cases"] == 0
    assert (
        bundle_manifest["trust_defensibility"]["evidence_warning_summary"]["status"]
        == "REVIEW REQUIRED"
    )
    assert bundle_manifest["trust_defensibility"]["sample_data_demo_note"]["is_demo_or_sample"] is (
        True
    )
    assert {artifact["id"] for artifact in bundle_manifest["generated_artifacts"]} >= {
        "operator_review_ui"
    }
    for artifact in bundle_manifest["generated_artifacts"]:
        assert artifact["opens_outside_ui"] is True
        assert artifact["ui_link_behavior"] == "link_when_present_else_unavailable_label"
        assert artifact["artifact_format"]
    checksum_manifest = _load_yaml(bundle_dir / "checksum_manifest.json")
    assert checksum_manifest["algorithm"] == "sha256"
    checksum_paths = {item["bundle_path"] for item in checksum_manifest["files"]}
    assert {
        "manifest.json",
        "README.md",
        "operator_review_ui.html",
        "operator_dashboard.md",
        "evidence_bundle_summary.md",
        "artifact_index.md",
        "inspection_constraint_audit.md",
    } <= checksum_paths
    verification = verify_evidence_bundle_checksums(bundle_dir)
    assert verification["ok"] is True
    assert verification["checksum_ok"] is True
    assert verification["scenario_metadata_ok"] is True
    assert verification["warnings"] == []

    missing_cfg = copy.deepcopy(cfg)
    missing_cfg.pop("evidence_bundle", None)
    for key in (
        "authorization_id",
        "authorization_authority",
        "approving_authority_source",
        "authorization_date_checked_utc",
        "authorization_expiration_date",
        "operator_confirmation_status",
        "operating_altitude_limit_m",
        "special_conditions_limitations",
        "emergency_contingency_plan",
    ):
        missing_cfg["regulatory"].pop(key, None)
    missing_cfg["regulatory"]["operating_time_window"] = {}
    missing_cfg["regulatory"]["required_crew_roles"] = []
    missing_dir = tmp_path / "missing_regulatory_evidence"
    missing_dir.mkdir()
    for artifact_name in (
        "plan.json",
        "inspection_constraint_audit.md",
        "inspection_constraint_audit.json",
        "what_if_plan.md",
        "what_if_plan.json",
        "score.json",
        "flight_path.png",
        "robustness.json",
        "operator_memo.md",
        "weather.json",
        "autopilot_mission.csv",
        "mission_review.kml",
        "flight_planning_exports.json",
        "flight_planning_exports.md",
    ):
        (missing_dir / artifact_name).write_bytes((tmp_path / artifact_name).read_bytes())
    export_regulatory_readiness_report(
        result.plan,
        result.sim_result,
        result.constraints,
        missing_dir,
        cfg=missing_cfg,
        robustness=result.robustness,
    )
    missing_evidence = export_operator_evidence_bundle(
        missing_dir,
        EXAMPLES_DIR / "bvlos_powerline_inspection_demo.yaml",
        cfg=missing_cfg,
    )

    assert missing_evidence["complete"] is True
    assert missing_evidence["bundle_completeness_score"] == 100.0
    assert missing_evidence["artifact_completeness"]["score"] == 100.0
    assert missing_evidence["regulatory_documentation_completeness"]["score"] == 0.0
    assert missing_evidence["operator_review"]["status"] == "draft"
    assert missing_evidence["regulatory_evidence_status"]["all_optional_fields_documented"] is (
        False
    )
    assert {item["id"] for item in missing_evidence["missing_evidence"]} >= {
        "authorization_id",
        "required_crew_roles",
    }
    missing_paths = {
        item["path"] for item in missing_evidence["regulatory_evidence_status"]["missing"]
    }
    assert {
        "regulatory.authorization_id",
        "regulatory.authorization_authority",
        "regulatory.approving_authority_source",
        "regulatory.authorization_date_checked_utc",
        "regulatory.authorization_expiration_date",
        "regulatory.operator_confirmation_status",
        "regulatory.operating_altitude_limit_m",
        "regulatory.operating_time_window",
        "regulatory.required_crew_roles",
        "regulatory.special_conditions_limitations",
        "regulatory.emergency_contingency_plan",
    } <= missing_paths
    attention_paths = {
        item["path"]
        for item in missing_evidence["regulatory_evidence_status"]["operator_attention_missing"]
    }
    assert {
        "regulatory.authorization_id",
        "regulatory.required_crew_roles",
        "regulatory.emergency_contingency_plan",
    } <= attention_paths
