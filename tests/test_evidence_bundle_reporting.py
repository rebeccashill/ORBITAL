from __future__ import annotations

import hashlib
import json
import os

from mission_framework.reporting.flight_output import (
    _artifact_freshness_metadata,
    _bundle_completeness,
    _dashboard_verdict,
    _format_artifact_index,
    _format_evidence_bundle_summary,
    _format_operator_evidence_dashboard,
    _regulatory_documentation_completeness,
    verify_evidence_bundle_checksums,
)
from mission_framework.reporting.operator_review_ui import format_operator_review_ui_html


def test_bundle_completeness_score_counts_present_expected_artifacts() -> None:
    completeness = _bundle_completeness(
        [
            {"id": "scenario_yaml", "present": True},
            {"id": "plan_json", "present": True},
            {"id": "flight_path_plot", "present": False},
        ]
    )

    assert completeness["score"] == 66.7
    assert completeness["unit"] == "percent"
    assert completeness["present_artifacts"] == 2
    assert completeness["total_artifacts"] == 3
    assert completeness["missing_artifacts"] == 1
    assert completeness["complete"] is False
    assert "Optional documentation fields are reported separately" in completeness["scoring_note"]


def test_bundle_completeness_score_is_complete_for_empty_artifact_set() -> None:
    completeness = _bundle_completeness([])

    assert completeness["score"] == 100.0
    assert completeness["present_artifacts"] == 0
    assert completeness["total_artifacts"] == 0
    assert completeness["missing_artifacts"] == 0
    assert completeness["complete"] is True


def test_regulatory_documentation_completeness_is_separate_from_artifact_score() -> None:
    completeness = _regulatory_documentation_completeness(
        {
            "field_count": 7,
            "missing_count": 2,
            "operator_attention_missing_count": 1,
        }
    )

    assert completeness["score"] == 71.4
    assert completeness["documented_fields"] == 5
    assert completeness["total_fields"] == 7
    assert completeness["missing_fields"] == 2
    assert completeness["operator_attention_missing_fields"] == 1
    assert completeness["complete"] is False
    assert completeness["documentation_only"] is True


def test_artifact_freshness_metadata_records_hashes_sizes_and_staleness(tmp_path) -> None:
    source = tmp_path / "inspection_constraint_audit.json"
    destination = tmp_path / "bundle" / "inspection_constraint_audit.json"
    destination.parent.mkdir()
    source.write_text('{"kind": "audit"}\n', encoding="utf-8")
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    os.utime(source, (100.0, 100.0))
    os.utime(destination, (110.0, 110.0))

    freshness = _artifact_freshness_metadata(
        source=source,
        destination=destination,
        present=True,
        scenario_modified_ts=120.0,
    )

    expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert freshness["source_sha256"] == expected_hash
    assert freshness["bundle_sha256"] == expected_hash
    assert freshness["source_size_bytes"] == source.stat().st_size
    assert freshness["bundle_size_bytes"] == destination.stat().st_size
    assert freshness["source_modified_utc"]
    assert freshness["bundle_modified_utc"]
    assert freshness["stale_against_scenario"] is True


def test_artifact_freshness_metadata_handles_missing_and_scenario_artifacts(tmp_path) -> None:
    scenario_source = tmp_path / "scenario.yaml"
    scenario_destination = tmp_path / "bundle" / "scenario.yaml"
    scenario_destination.parent.mkdir()
    scenario_source.write_text("scenario:\n  name: Demo\n", encoding="utf-8")
    scenario_destination.write_text(scenario_source.read_text(encoding="utf-8"), encoding="utf-8")
    os.utime(scenario_source, (100.0, 100.0))
    os.utime(scenario_destination, (100.0, 100.0))

    scenario_freshness = _artifact_freshness_metadata(
        source=scenario_source,
        destination=scenario_destination,
        present=True,
        scenario_modified_ts=120.0,
    )
    missing_freshness = _artifact_freshness_metadata(
        source=tmp_path / "missing.json",
        destination=tmp_path / "bundle" / "missing.json",
        present=False,
        scenario_modified_ts=120.0,
    )

    assert scenario_freshness["stale_against_scenario"] is False
    assert missing_freshness["source_sha256"] is None
    assert missing_freshness["bundle_sha256"] is None
    assert missing_freshness["stale_against_scenario"] is False


def test_artifact_index_lists_expected_and_generated_bundle_artifacts() -> None:
    markdown = _format_artifact_index(
        {
            "artifacts": [
                {
                    "id": "scenario_yaml",
                    "label": "Scenario YAML",
                    "bundle_path": "scenario.yaml",
                    "present": True,
                },
                {
                    "id": "flight_path_plot",
                    "label": "Flight path plot",
                    "bundle_path": "flight path.png",
                    "present": False,
                },
            ],
            "generated_artifacts": [
                {
                    "id": "artifact_index",
                    "label": "Evidence bundle artifact index",
                    "bundle_path": "artifact_index.md",
                    "present": True,
                    "generated": True,
                },
            ],
        }
    )

    assert "# Evidence Bundle Artifact Index" in markdown
    assert "Open First" in markdown
    assert "[operator_dashboard.md](operator_dashboard.md) is the first review surface" in markdown
    assert "Review Path" in markdown
    assert "Artifact Status Summary" in markdown
    assert "Expected artifacts included: 1 / 2" in markdown
    assert "Expected artifacts missing: 1" in markdown
    assert "Recommended Opening Order" in markdown
    assert "1. [operator_dashboard.md](operator_dashboard.md)" in markdown
    assert "| Artifact | Status | Link | Type |" in markdown
    assert "| Scenario YAML | included | [scenario.yaml](scenario.yaml) | expected |" in markdown
    assert "| Flight path plot | missing | flight path.png | expected |" in markdown
    assert (
        "| Evidence bundle artifact index | included | "
        "[artifact_index.md](artifact_index.md) | generated |"
    ) in markdown


def test_dashboard_verdict_uses_consistent_release_language() -> None:
    assert (
        _dashboard_verdict(
            mission_status="MODIFY",
            regulatory_state="OPERATOR_ACTION_REQUIRED",
            missing_evidence_count=0,
            warning_count=0,
        )["label"]
        == "MODIFY"
    )
    assert (
        _dashboard_verdict(
            mission_status="GO",
            regulatory_state="OPERATOR_ACTION_REQUIRED",
            missing_evidence_count=0,
            warning_count=0,
        )["label"]
        == "REVIEW REQUIRED"
    )
    assert (
        _dashboard_verdict(
            mission_status="GO",
            regulatory_state="DOCUMENTED_REVIEW_REQUIRED",
            missing_evidence_count=0,
            warning_count=0,
        )["label"]
        == "GO"
    )


def test_operator_dashboard_summarizes_review_state_and_artifact_links() -> None:
    markdown = _format_operator_evidence_dashboard(
        {
            "scenario_path": "examples/bvlos_powerline_inspection_demo.yaml",
            "constraint_audit": {
                "mission_id": "BVLOS Powerline Inspection Demo",
                "status": "go",
                "mission_risk": "low",
                "top_limiting_constraint": {
                    "label": "Wind / weather margin",
                    "status": "pass",
                    "margin": {"value": 3.1, "unit": "m/s"},
                },
            },
            "regulatory_readiness": {"readiness_state": "operator_action_required"},
            "bundle_completeness": {
                "score": 100.0,
                "present_artifacts": 17,
                "total_artifacts": 17,
            },
            "regulatory_documentation_completeness": {
                "score": 100.0,
                "documented_fields": 7,
                "total_fields": 7,
            },
            "operator_review": {
                "status": "ready_for_review",
                "reviewer_name": "Demo reviewer",
                "review_timestamp_utc": "2026-09-12T18:00:00Z",
                "review_notes": "Ready for operational review.",
                "operator_decision": "pending operator review",
            },
            "missing_evidence": [],
            "bundle_warnings": [],
            "weather": {
                "source": "offline Open-Meteo-shaped sample",
                "timestamp_utc": "2026-09-12T18:00:00Z",
                "fallback_used": True,
                "fallback_reason": "weather.use_live is false",
                "live_fetch_enabled": False,
            },
            "trust_defensibility": {
                "sample_data_demo_note": {"note": "Sample data / demo scenario: demo inputs only."},
                "weather_fallback_status": {
                    "status": "FALLBACK USED",
                    "summary": (
                        "FALLBACK USED: source offline Open-Meteo-shaped sample, "
                        "timestamp 2026-09-12T18:00:00Z"
                    ),
                    "operator_action": "Refresh current field weather.",
                },
                "uncertainty_robustness_status": {
                    "status": "PASS",
                    "summary": "PASS: 20 case(s), hard pass rate 100.0 %, worst hard margin 0.1",
                    "operator_action": "Review robustness assumptions.",
                },
                "evidence_warning_summary": {
                    "status": "CLEAR",
                    "summary": (
                        "CLEAR: 0 missing artifact(s), 0 stale artifact(s), "
                        "0 missing evidence item(s), 0 bundle warning(s)"
                    ),
                    "missing_artifacts": 0,
                    "stale_artifacts": 0,
                    "missing_evidence": 0,
                    "bundle_warnings": 0,
                },
                "model_assumptions_summary": [
                    {
                        "label": "Battery / energy model",
                        "assumption": "Battery reserve comes from configured scenario inputs.",
                        "operator_review_note": "Confirm battery health before release.",
                    }
                ],
                "known_limitations_summary": [
                    {
                        "id": "offline_sample_weather",
                        "applies": True,
                        "limitation": "Weather may come from offline, fallback, or sample inputs.",
                    }
                ],
            },
            "artifacts": [
                {
                    "id": "constraint_audit_markdown",
                    "label": "Primary constraint-audit report",
                    "bundle_path": "inspection_constraint_audit.md",
                    "present": True,
                },
                {
                    "id": "what_if_plan_markdown",
                    "label": "What-if planning report",
                    "bundle_path": "what_if_plan.md",
                    "present": True,
                },
                {
                    "id": "regulatory_readiness_markdown",
                    "label": "Regulatory readiness report",
                    "bundle_path": "regulatory_readiness_report.md",
                    "present": True,
                },
                {
                    "id": "flight_path_plot",
                    "label": "Flight path plot",
                    "bundle_path": "flight_path.png",
                    "present": True,
                },
                {
                    "id": "autopilot_mission_csv",
                    "label": "Autopilot mission CSV",
                    "bundle_path": "autopilot_mission.csv",
                    "present": True,
                },
                {
                    "id": "mission_review_kml",
                    "label": "Mission review KML",
                    "bundle_path": "mission_review.kml",
                    "present": True,
                },
            ],
            "generated_artifacts": [
                {
                    "id": "manifest_json",
                    "label": "Evidence bundle manifest",
                    "bundle_path": "manifest.json",
                    "present": True,
                    "generated": True,
                },
                {
                    "id": "checksum_manifest",
                    "label": "Evidence bundle checksum manifest",
                    "bundle_path": "checksum_manifest.json",
                    "present": True,
                    "generated": True,
                },
            ],
        }
    )

    assert "# ORBITAL Operator Evidence Dashboard" in markdown
    assert "Mission Verdict: REVIEW REQUIRED" in markdown
    assert "Modeled feasibility is acceptable" in markdown
    assert "Mission Card" in markdown
    assert "| Verdict | REVIEW REQUIRED |" in markdown
    assert "| Modeled mission status | GO |" in markdown
    assert "| Evidence completeness | 100.0 % (17 / 17 artifacts present) |" in markdown
    assert "| Weather fallback status | FALLBACK USED |" in markdown
    assert "Robustness status" in markdown
    assert "PASS: 20 case(s), hard pass rate 100.0 %" in markdown
    assert "Decision-Support Boundary" in markdown
    assert "10-Second Mission Read" in markdown
    assert "Trust And Defensibility" in markdown
    assert "Sample Data / Demo Scenario Note" in markdown
    assert "Model Assumptions Summary" in markdown
    assert "Battery reserve comes from configured scenario inputs." in markdown
    assert "Known Limitations Summary" in markdown
    assert "offline_sample_weather" in markdown
    assert "Evidence Warnings At A Glance" in markdown
    assert "CLEAR: 0 missing artifact(s), 0 stale artifact(s)" in markdown
    assert "Mission status: GO" in markdown
    assert "Mission risk: LOW" in markdown
    assert "Top limiting constraint: Wind / weather margin, PASS, margin 3.1 m/s" in markdown
    assert "Regulatory readiness: OPERATOR_ACTION_REQUIRED" in markdown
    assert "Bundle completeness: 100.0 % (17 / 17 artifacts present)" in markdown
    assert "Regulatory documentation completeness: 100.0 % (7 / 7 fields documented)" in markdown
    assert "| Signal | Current value | Operator cue |" in markdown
    assert "Recommended Opening Sequence" in markdown
    assert "Bundle warnings: 0" in markdown
    assert "Review status: ready for review" in markdown
    assert "Reviewer name: Demo reviewer" in markdown
    assert "Operator decision: pending operator review" in markdown
    assert "Review notes: Ready for operational review." in markdown
    assert "not approval, not authorization, not legal advice" in markdown
    assert (
        "Review fields are documentation-only records; they do not change release authority."
        in markdown
    )
    assert "Feasibility And Decision Support" in markdown
    assert "Evidence Package" in markdown
    assert "Route, Export, And Field-Use Artifacts" in markdown
    assert "[inspection_constraint_audit.md](inspection_constraint_audit.md)" in markdown
    assert "[what_if_plan.md](what_if_plan.md)" in markdown
    assert "[regulatory_readiness_report.md](regulatory_readiness_report.md)" in markdown
    assert "[manifest.json](manifest.json)" in markdown
    assert "[checksum_manifest.json](checksum_manifest.json)" in markdown
    assert "[flight_path.png](flight_path.png)" in markdown
    assert "[autopilot_mission.csv](autopilot_mission.csv)" in markdown
    assert "[mission_review.kml](mission_review.kml)" in markdown


def test_operator_review_ui_renders_first_screen_and_product_boundary() -> None:
    html = format_operator_review_ui_html(
        {
            "scenario_path": "examples/bvlos_powerline_inspection_demo.yaml",
            "constraint_audit": {
                "mission_id": "BVLOS Powerline Inspection Demo",
                "status": "go",
                "mission_risk": "low",
                "top_limiting_constraint": {
                    "label": "Wind / weather margin",
                    "status": "pass",
                    "margin": {"value": 3.1, "unit": "m/s"},
                },
            },
            "regulatory_readiness": {"readiness_state": "operator_action_required"},
            "bundle_completeness": {
                "score": 100.0,
                "present_artifacts": 18,
                "total_artifacts": 18,
            },
            "regulatory_documentation_completeness": {
                "score": 85.7,
                "documented_fields": 6,
                "total_fields": 7,
            },
            "operator_review": {
                "status": "ready_for_review",
                "reviewer_name": "Demo reviewer",
                "review_timestamp_utc": "2026-09-12T18:00:00Z",
                "operator_decision": "pending operator review",
            },
            "missing_evidence": [],
            "bundle_warnings": [],
            "trust_defensibility": {
                "weather_fallback_status": {
                    "status": "fallback_used",
                    "summary": "Fallback weather sample was used.",
                },
                "uncertainty_robustness_status": {
                    "status": "pass",
                    "summary": "Robustness cases passed.",
                },
                "evidence_warning_summary": {
                    "status": "clear",
                    "summary": (
                        "CLEAR: 0 missing artifact(s), 0 stale artifact(s), "
                        "0 missing evidence item(s), 0 bundle warning(s)"
                    ),
                    "missing_artifacts": 0,
                    "stale_artifacts": 0,
                    "missing_evidence": 0,
                    "bundle_warnings": 0,
                },
            },
            "artifacts": [
                {
                    "id": "flight_path_plot",
                    "label": "Flight path plot",
                    "bundle_path": "flight_path.png",
                    "present": True,
                }
            ],
            "generated_artifacts": [
                {
                    "id": "operator_dashboard",
                    "label": "Operator evidence dashboard",
                    "bundle_path": "operator_dashboard.md",
                    "present": True,
                    "generated": True,
                },
                {
                    "id": "constraint_audit_markdown",
                    "label": "Primary constraint-audit report",
                    "bundle_path": "inspection_constraint_audit.md",
                    "present": True,
                    "generated": True,
                },
                {
                    "id": "manifest_json",
                    "label": "Evidence bundle manifest",
                    "bundle_path": "manifest.json",
                    "present": True,
                    "generated": True,
                },
                {
                    "id": "checksum_manifest",
                    "label": "Evidence bundle checksum manifest",
                    "bundle_path": "checksum_manifest.json",
                    "present": True,
                    "generated": True,
                },
            ],
        }
    )

    assert "ORBITAL Operator Review UI" in html
    assert "Mission Verdict:" in html
    assert "REVIEW REQUIRED" in html
    assert "Next operator action" in html
    assert "Modeled mission status" in html
    assert "Mission risk" in html
    assert "Top limiting constraint" in html
    assert "Regulatory readiness" in html
    assert "Evidence completeness" in html
    assert "Regulatory documentation" in html
    assert "Weather fallback" in html
    assert "Robustness / uncertainty" in html
    assert "Missing evidence" in html
    assert "Evidence warnings" in html
    assert "local review surface" in html
    assert "decision support, not approval" in html
    assert "not approval, authorization, LAANC, legal advice, or operational clearance" in html
    assert "does not approve a mission" in html
    assert "documentation-only" in html
    assert "Markdown, JSON, CSV, KML, and checksum artifacts remain accessible" in html
    assert 'src="flight_path.png"' in html
    assert 'href="operator_dashboard.md"' in html
    assert 'href="manifest.json"' in html
    assert "Demo reviewer" in html


def test_evidence_bundle_summary_highlights_reviewer_snapshot_and_flow() -> None:
    markdown = _format_evidence_bundle_summary(
        {
            "scenario_path": "examples/bvlos_powerline_inspection_demo.yaml",
            "bundle_completeness": {
                "score": 100.0,
                "present_artifacts": 17,
                "total_artifacts": 17,
                "missing_artifacts": 0,
            },
            "artifact_completeness": {
                "score": 100.0,
                "present_artifacts": 17,
                "total_artifacts": 17,
            },
            "regulatory_documentation_completeness": {
                "score": 85.7,
                "documented_fields": 6,
                "total_fields": 7,
            },
            "operator_review": {
                "status": "ready_for_review",
                "operator_decision": "pending operator review",
                "reviewer_name": "Demo reviewer",
                "review_timestamp_utc": "2026-09-12T18:00:00Z",
                "review_notes": "Ready for operational review.",
            },
            "missing_evidence": [],
            "bundle_warnings": [],
            "freshness": {
                "generated_timestamp_utc": "2026-09-12T18:00:00Z",
                "orbital_version": "1.0.10",
                "scenario_hash": {"value": "a" * 64},
                "command": {"display": "python -m mission_framework.cli demo.yaml"},
            },
            "weather": {
                "source": "offline Open-Meteo-shaped sample",
                "timestamp_utc": "2026-09-12T18:00:00Z",
                "fallback_used": True,
            },
            "trust_defensibility": {
                "sample_data_demo_note": {"note": "Sample data / demo scenario: demo inputs only."},
                "weather_fallback_status": {
                    "status": "FALLBACK USED",
                    "summary": (
                        "FALLBACK USED: source offline Open-Meteo-shaped sample, "
                        "timestamp 2026-09-12T18:00:00Z"
                    ),
                    "operator_action": "Refresh current field weather.",
                },
                "uncertainty_robustness_status": {
                    "summary": "PASS: 20 case(s), hard pass rate 100.0 %",
                },
                "evidence_warning_summary": {
                    "summary": (
                        "CLEAR: 0 missing artifact(s), 0 stale artifact(s), "
                        "0 missing evidence item(s), 0 bundle warning(s)"
                    ),
                },
            },
            "regulatory_evidence_status": {"missing": []},
            "approval_checklist": {"item_count": 9},
        }
    )

    assert "# Evidence Bundle Summary" in markdown
    assert "Reviewer Snapshot" in markdown
    assert "| Open first | [operator_dashboard.md](operator_dashboard.md)" in markdown
    assert "Recommended Review Flow" in markdown
    assert "Open the operator dashboard for the 10-second mission read." in markdown
    assert "What-if plan: [what_if_plan.md](what_if_plan.md)" in markdown
    assert "Regulatory readiness report: [regulatory_readiness_report.md]" in markdown
    assert "ORBITAL version: 1.0.10" in markdown
    assert "Trust And Defensibility" in markdown
    assert "Sample data / demo scenario note" in markdown
    assert "Weather fallback status: FALLBACK USED" in markdown
    assert "Uncertainty / robustness status: PASS: 20 case(s)" in markdown


def test_verify_evidence_bundle_checksums_detects_clean_and_tampered_bundle(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "scenario.yaml").write_text("scenario:\n  name: Demo\n", encoding="utf-8")
    (bundle_dir / "artifact.md").write_text("original\n", encoding="utf-8")
    scenario_hash = hashlib.sha256((bundle_dir / "scenario.yaml").read_bytes()).hexdigest()
    artifact_hash = hashlib.sha256((bundle_dir / "artifact.md").read_bytes()).hexdigest()
    artifact_size = (bundle_dir / "artifact.md").stat().st_size
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "freshness": {"scenario_hash": {"algorithm": "sha256", "value": scenario_hash}},
                "artifacts": [
                    {
                        "id": "artifact",
                        "bundle_path": "artifact.md",
                        "present": True,
                        "freshness": {"stale_against_scenario": False},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "checksum_manifest.json").write_text(
        json.dumps(
            {
                "kind": "evidence_bundle_checksum_manifest",
                "algorithm": "sha256",
                "files": [
                    {
                        "bundle_path": "artifact.md",
                        "sha256": artifact_hash,
                        "size_bytes": artifact_size,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    clean = verify_evidence_bundle_checksums(bundle_dir)

    assert clean["ok"] is True
    assert clean["checksum_ok"] is True
    assert clean["scenario_metadata_ok"] is True
    assert clean["warnings"] == []

    (bundle_dir / "artifact.md").write_text("tampered\n", encoding="utf-8")
    tampered = verify_evidence_bundle_checksums(bundle_dir)

    assert tampered["ok"] is False
    assert tampered["checksum_ok"] is False
    assert tampered["mismatched_files"][0]["bundle_path"] == "artifact.md"
    assert {warning["kind"] for warning in tampered["warnings"]} >= {"checksum_mismatch"}


def test_verify_evidence_bundle_checksums_detects_scenario_metadata_mismatch(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "scenario.yaml").write_text("scenario:\n  name: Changed\n", encoding="utf-8")
    scenario_hash = "0" * 64
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "freshness": {"scenario_hash": {"algorithm": "sha256", "value": scenario_hash}},
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "checksum_manifest.json").write_text(
        json.dumps({"kind": "evidence_bundle_checksum_manifest", "files": []}),
        encoding="utf-8",
    )

    result = verify_evidence_bundle_checksums(bundle_dir)

    assert result["ok"] is False
    assert result["scenario_metadata_ok"] is False
    assert {warning["kind"] for warning in result["warnings"]} >= {"scenario_metadata_mismatch"}


def test_verify_evidence_bundle_checksums_reports_missing_checksum_manifest(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    scenario_path = bundle_dir / "scenario.yaml"
    scenario_path.write_text("scenario:\n  name: Demo\n", encoding="utf-8")
    scenario_hash = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "freshness": {"scenario_hash": {"algorithm": "sha256", "value": scenario_hash}},
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    result = verify_evidence_bundle_checksums(bundle_dir)

    assert result["ok"] is False
    assert result["checksum_ok"] is True
    assert result["scenario_metadata_ok"] is True
    assert {warning["kind"] for warning in result["warnings"]} >= {"missing_artifact"}
