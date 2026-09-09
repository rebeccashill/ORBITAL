from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from scripts.run_baselines import (
    FIELDNAMES,
    earliest_deadline_assignment,
    greedy_aircraft_assignment,
    write_csv,
    write_markdown,
)


def test_greedy_aircraft_assignment_uses_nearest_neighbor_order() -> None:
    cfg = {
        "initial_state": {"x_m": 0.0, "y_m": 0.0},
        "mission": {
            "waypoints": [
                {"id": "FAR", "x_m": 100.0, "y_m": 0.0},
                {"id": "NEAR", "x_m": 10.0, "y_m": 0.0},
                {"id": "NEXT", "x_m": 20.0, "y_m": 0.0},
            ]
        },
        "vehicle": {
            "min_speed_mps": 5.0,
            "max_speed_mps": 10.0,
            "cruise_speed_mps": 50.0,
        },
    }

    assignment = greedy_aircraft_assignment(cfg)

    assert assignment["visit_order"] == ["NEAR", "NEXT", "FAR"]
    np.testing.assert_allclose(assignment["cruise_speed_mps"], np.array([10.0]))


def test_earliest_deadline_assignment_selects_targets_by_declared_deadline() -> None:
    cfg = {
        "mission": {
            "targets": [
                {
                    "id": "LATE",
                    "time_windows": [{"end_utc": "2026-01-07T23:59:59Z"}],
                },
                {
                    "id": "FIRST",
                    "time_windows": [{"end_utc": "2026-01-03T23:59:59Z"}],
                },
                {"id": "NO_WINDOW"},
            ]
        }
    }

    assignment = earliest_deadline_assignment(cfg)
    select_keys = [key for key in assignment.values if key.startswith("select_")]

    assert select_keys == ["select_FIRST", "select_LATE", "select_NO_WINDOW"]
    assert assignment["downlink_policy"] == 0
    np.testing.assert_allclose(assignment["obs_offset_FIRST"], np.array([0.0]))


def test_baseline_report_writers_include_comparison_fields(tmp_path: Path) -> None:
    row = {field: "" for field in FIELDNAMES}
    row.update(
        {
            "domain": "aircraft",
            "scenario": "Demo",
            "planner": "random_search",
            "category": "baseline",
            "samples": 3,
            "iterations": 0,
            "restarts": 1,
            "seed": 0,
            "score": 12.5,
            "feasible": True,
            "objective_cost": 12.5,
            "constraint_penalty": 0.0,
            "worst_hard_constraint": "battery_nonnegative",
            "worst_hard_margin": 1.0,
            "runtime_s": 0.25,
            "robustness_cases": 2,
            "robust_hard_pass_rate": 1.0,
            "robust_worst_hard_margin": 1.0,
            "robust_score": 12.5,
        }
    )

    csv_path = tmp_path / "baselines.csv"
    markdown_path = tmp_path / "baselines.md"

    write_csv([row], csv_path)
    write_markdown([row], markdown_path, "python scripts/run_baselines.py")

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows[0]["planner"] == "random_search"
    assert rows[0]["runtime_s"] == "0.25"

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "`random_search`" in markdown
    assert "Hard Pass Rate" in markdown
