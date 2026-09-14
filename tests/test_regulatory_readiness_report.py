from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mission_framework.core.types import Plan, SimResult
from mission_framework.reporting.flight_output import (
    build_regulatory_readiness_report,
    export_regulatory_readiness_report,
)


def _unit_plan() -> Plan:
    return Plan(
        kind="aircraft",
        waypoints=[
            {"id": "START", "x_m": 0.0, "y_m": 0.0, "z_m": 90.0},
            {"id": "TOWER_01", "x_m": 500.0, "y_m": 50.0, "z_m": 90.0},
        ],
        metadata={"mission_id": "unit_regulatory_mission"},
    )


def _unit_sim() -> SimResult:
    return SimResult(
        t=np.array([0.0, 60.0]),
        scalars={
            "t_end_s": 60.0,
            "energy_used_Wh": 12.5,
            "final_battery_Wh": 220.0,
            "waypoints_completed": 1.0,
            "waypoints_total": 1.0,
        },
    )


def _regulatory_cfg() -> dict[str, object]:
    return {
        "vehicle": {"battery_reserve_Wh": 150.0},
        "regulatory": {
            "laanc_required": True,
            "waiver_or_authorization_required": True,
            "airspace_class": "Class C",
            "visual_observer_required": True,
            "ground_risk_population_note": "Industrial corridor with sparse pedestrian exposure.",
            "authorization_id": "unit test authorization reference",
            "authorization_authority": "FAA / LAANC provider placeholder",
            "approving_authority_source": "Operator authorization binder",
            "authorization_date_checked_utc": "2026-09-11T16:30:00Z",
            "authorization_expiration_date": "2026-09-30",
            "operator_confirmation_status": "pending_operator_confirmation",
            "operating_altitude_limit_m": 110.0,
            "operating_time_window": {
                "start_utc": "2026-09-11T17:00:00Z",
                "end_utc": "2026-09-11T18:00:00Z",
            },
            "required_crew_roles": ["Remote pilot in command", "Visual observer"],
            "special_conditions_limitations": ["Maintain corridor containment."],
            "emergency_contingency_plan": "Review lost-link and recovery procedures.",
            "operating_assumptions": ["PIC verifies current restrictions before launch."],
            "unresolved_items": ["Confirm site access approval."],
        },
    }


def test_regulatory_readiness_report_documents_required_items_and_checklist() -> None:
    report = build_regulatory_readiness_report(
        _unit_plan(),
        _unit_sim(),
        cfg=_regulatory_cfg(),
        robustness={"cases": 2},
    )

    assert report["kind"] == "regulatory_readiness_report"
    assert report["mission_id"] == "unit_regulatory_mission"
    assert report["decision_support_only"] is True
    assert report["not_legal_approval"] is True
    assert "not legal approval" in report["disclaimer"]
    assert report["status"] == "operator_action_required"
    assert report["regulatory_summary"]["laanc_required"]["status"] == "required"
    assert report["regulatory_summary"]["waiver_or_authorization_required"]["status"] == "required"
    assert report["regulatory_summary"]["airspace_class"]["configured"] == "Class C"
    assert report["regulatory_summary"]["visual_observer_required"]["status"] == "required"

    evidence = report["regulatory_evidence"]
    assert evidence["documentation_only"] is True
    assert evidence["authorization_id"] == "unit test authorization reference"
    assert evidence["authorization_authority"] == "FAA / LAANC provider placeholder"
    assert evidence["approving_authority_source"] == "Operator authorization binder"
    assert evidence["authorization_date_checked_utc"] == "2026-09-11T16:30:00Z"
    assert evidence["authorization_expiration_date"] == "2026-09-30"
    assert evidence["operator_confirmation_status"] == "pending_operator_confirmation"
    assert evidence["operating_altitude_limit_m"] == 110.0
    assert evidence["operating_time_window"]["start_utc"] == "2026-09-11T17:00:00Z"
    assert evidence["required_crew_roles"] == [
        "Remote pilot in command",
        "Visual observer",
    ]
    assert evidence["special_conditions_limitations"] == [
        "Maintain corridor containment.",
    ]
    assert evidence["emergency_contingency_plan"] == "Review lost-link and recovery procedures."

    checklist_ids = {item["id"] for item in report["operator_approval_checklist"]}
    assert {
        "laanc_confirmation",
        "waiver_authorization_confirmation",
        "visual_observer_assignment",
        "crew_briefing",
        "emergency_contingency_plan",
        "notam_local_restriction_review",
        "weather_minimums_confirmation",
        "battery_reserve_confirmation",
    } <= checklist_ids
    assert all(item["checked"] is False for item in report["operator_approval_checklist"])

    unresolved_ids = {item["id"] for item in report["unresolved_regulatory_items"]}
    assert "operator_provided_item_1" in unresolved_ids
    assert "laanc_authorization_confirmation" in unresolved_ids
    assert "waiver_or_authorization_confirmation" in unresolved_ids
    assert "visual_observer_staffing_plan" in unresolved_ids


def test_regulatory_readiness_export_writes_json_and_markdown(tmp_path: Path) -> None:
    cfg = _regulatory_cfg()
    report = export_regulatory_readiness_report(
        _unit_plan(),
        _unit_sim(),
        None,
        tmp_path,
        cfg=cfg,
        robustness={"cases": 1},
    )

    json_path = tmp_path / "regulatory_readiness_report.json"
    md_path = tmp_path / "regulatory_readiness_report.md"
    assert json_path.is_file()
    assert md_path.is_file()

    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_payload["kind"] == "regulatory_readiness_report"
    assert json_payload["not_legal_approval"] is True
    assert (
        json_payload["regulatory_evidence"]["authorization_id"]
        == "unit test authorization reference"
    )
    assert json_payload["operator_approval_checklist"] == report["operator_approval_checklist"]

    markdown = md_path.read_text(encoding="utf-8")
    assert "# Regulatory Readiness Report" in markdown
    assert "ORBITAL provides decision support only and is not legal approval" in markdown
    assert "unit test authorization reference" in markdown
    assert "FAA / LAANC provider placeholder" in markdown
    assert "2026-09-11T16:30:00Z" in markdown
    assert "pending_operator_confirmation" in markdown
    assert "Regulatory Evidence Fields" in markdown
    assert "Review lost-link and recovery procedures." in markdown
    assert "- [ ] Confirm LAANC / controlled-airspace authorization" in markdown
    assert "- [ ] Confirm waiver / authorization coverage" in markdown
    assert "- [ ] Confirm visual observer assignment" in markdown


def test_regulatory_readiness_omits_conditional_checklist_items_when_not_required() -> None:
    cfg = _regulatory_cfg()
    regulatory = cfg["regulatory"]
    assert isinstance(regulatory, dict)
    regulatory["laanc_required"] = False
    regulatory["waiver_or_authorization_required"] = False
    regulatory["visual_observer_required"] = False

    report = build_regulatory_readiness_report(_unit_plan(), cfg=cfg)

    checklist_ids = {item["id"] for item in report["operator_approval_checklist"]}
    assert "laanc_confirmation" not in checklist_ids
    assert "waiver_authorization_confirmation" not in checklist_ids
    assert "visual_observer_assignment" not in checklist_ids
    assert {
        "crew_briefing",
        "emergency_contingency_plan",
        "notam_local_restriction_review",
        "weather_minimums_confirmation",
        "battery_reserve_confirmation",
    } <= checklist_ids
