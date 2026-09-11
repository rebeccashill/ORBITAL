from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.run_optimizer_maturity import (
    FIELDNAMES,
    aircraft_exhaustive_assignments,
    spacecraft_exhaustive_assignments,
    write_csv,
    write_markdown,
)


def test_aircraft_exhaustive_grid_enumerates_orders_and_speeds() -> None:
    cfg = {
        "mission": {
            "waypoints": [
                {"id": "A"},
                {"id": "B"},
            ]
        },
        "vehicle": {"min_speed_mps": 10.0, "max_speed_mps": 20.0},
    }

    assignments = aircraft_exhaustive_assignments(cfg, speed_grid=3)

    assert len(assignments) == 6
    assert {tuple(a["visit_order"]) for a in assignments} == {("A", "B"), ("B", "A")}
    speeds = sorted({float(np.array(a["cruise_speed_mps"]).reshape(-1)[0]) for a in assignments})
    assert speeds == [10.0, 15.0, 20.0]


def test_spacecraft_exhaustive_grid_enumerates_target_choices_offsets_and_policies() -> None:
    cfg = {"mission": {"targets": [{"id": "T1"}, {"id": "T2"}]}}

    assignments = spacecraft_exhaustive_assignments(cfg, offset_grid=3)

    assert len(assignments) == 48
    assert {int(a["downlink_policy"]) for a in assignments} == {0, 1, 2}
    assert any(int(a["select_T1"]) == 0 and int(a["select_T2"]) == 0 for a in assignments)
    assert any(
        int(a["select_T1"]) == 1
        and int(a["select_T2"]) == 1
        and float(np.array(a["obs_offset_T1"]).reshape(-1)[0]) == 1.0
        and float(np.array(a["obs_offset_T2"]).reshape(-1)[0]) == 1.0
        for a in assignments
    )


def test_optimizer_maturity_report_documents_solver_style_limits(tmp_path: Path) -> None:
    row = {field: "" for field in FIELDNAMES}
    row.update(
        {
            "scenario_group": "stress",
            "domain": "spacecraft",
            "scenario": "CubeSat Stress",
            "scenario_file": "examples/stress/spacecraft_power_starved.yaml",
            "planner": "exhaustive_grid",
            "category": "solver_style",
            "candidate_evaluations": 192,
            "score": -33.0,
            "feasible": True,
            "objective_cost": -33.0,
            "constraint_penalty": 0.0,
            "worst_hard_constraint": "battery_nonnegative",
            "worst_hard_margin": 1.0,
            "runtime_s": 0.5,
            "robustness_cases": 3,
            "robust_hard_pass_rate": 1.0,
            "robust_worst_hard_margin": 1.0,
            "robust_score": -33.0,
            "notes": "Enumerated 192 candidates.",
        }
    )

    csv_path = tmp_path / "optimizer_maturity.csv"
    markdown_path = tmp_path / "optimizer_maturity.md"

    write_csv([row], csv_path)
    write_markdown([row], markdown_path, "python scripts/run_optimizer_maturity.py")

    assert "exhaustive_grid" in csv_path.read_text(encoding="utf-8")

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "exhaustive_grid" in markdown
    assert "not yet production-grade mission planning" in markdown
    assert "high-wind, tight-geofence, power-starved, and slew-constrained" in markdown
