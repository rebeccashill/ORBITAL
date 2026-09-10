from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from mission_framework.core.constraints import evaluate_constraints
from mission_framework.core.decision_variables import DecisionAssignment
from mission_framework.core.types import EventType
from mission_framework.scenario_validation import collect_scenario_validation_issues
from mission_framework.spacecraft.mission import build_problem_from_config

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _load_spacecraft_demo() -> dict[str, Any]:
    return yaml.safe_load((EXAMPLES / "cubesat_leo_demo.yaml").read_text(encoding="utf-8"))


def _assignment_for_target(cfg: dict[str, Any], selected_target: str) -> DecisionAssignment:
    values: dict[str, Any] = {"downlink_policy": 0}
    for target in cfg["mission"]["targets"]:
        target_id = str(target["id"])
        values[f"select_{target_id}"] = 1 if target_id == selected_target else 0
        values[f"obs_offset_{target_id}"] = np.array([0.0])
    return DecisionAssignment(values=values)


def _as_utc(text: str) -> datetime:
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_at(epoch_utc: str, seconds: float) -> str:
    return (
        (_as_utc(epoch_utc) + timedelta(seconds=float(seconds))).isoformat().replace("+00:00", "Z")
    )


def _visibility_windows_for_target(
    cfg: dict[str, Any], target_id: str
) -> list[tuple[float, float]]:
    relaxed = copy.deepcopy(cfg)
    relaxed.setdefault("constraints", {})["enforce_target_time_windows"] = False
    problem = build_problem_from_config(relaxed)
    plan = problem.build_plan(_assignment_for_target(relaxed, target_id))
    sim = problem.simulate(plan, np.random.default_rng(0))
    return [tuple(window) for window in sim.metadata["target_visibility_windows"][target_id]]


def _later_schedulable_window(cfg: dict[str, Any], target_id: str) -> tuple[float, float]:
    windows = _visibility_windows_for_target(cfg, target_id)
    obs_duration_s = float(cfg["mission"]["targets"][0].get("obs_duration_s", 30.0))
    schedulable = [window for window in windows if window[1] - window[0] >= obs_duration_s]
    assert len(schedulable) >= 2
    return schedulable[1]


def test_spacecraft_scheduler_enforces_declared_target_time_windows() -> None:
    cfg = _load_spacecraft_demo()
    cfg.setdefault("constraints", {})["enforce_target_time_windows"] = True

    target_id = "TGT1"
    window_start_s, window_end_s = _later_schedulable_window(cfg, target_id)
    epoch = str(cfg["orbit"]["epoch_utc"])
    cfg["mission"]["targets"][0]["time_windows"] = [
        {
            "start_utc": _iso_at(epoch, window_start_s),
            "end_utc": _iso_at(epoch, window_end_s),
        }
    ]

    problem = build_problem_from_config(cfg)
    plan = problem.build_plan(_assignment_for_target(cfg, target_id))
    sim = problem.simulate(plan, np.random.default_rng(0))
    report = evaluate_constraints(sim, problem.constraints)
    observations = [event for event in plan.schedule.events if event.etype == EventType.OBSERVATION]

    assert len(observations) == 1
    assert observations[0].t_start + 1e-9 >= window_start_s
    assert observations[0].t_end <= window_end_s + 1e-9
    assert sim.metadata["target_time_windows_enforced"] is True
    assert sim.scalars["target_time_window_violation_s"] == pytest.approx(0.0)
    assert report.by_name()["target_time_windows"].is_satisfied is True


def test_spacecraft_target_time_windows_can_be_metadata_only_when_disabled() -> None:
    cfg = _load_spacecraft_demo()
    cfg.setdefault("constraints", {})["enforce_target_time_windows"] = False

    target_id = "TGT1"
    raw_first_window = _visibility_windows_for_target(cfg, target_id)[0]
    enforced_window_start_s, enforced_window_end_s = _later_schedulable_window(cfg, target_id)
    epoch = str(cfg["orbit"]["epoch_utc"])
    cfg["mission"]["targets"][0]["time_windows"] = [
        {
            "start_utc": _iso_at(epoch, enforced_window_start_s),
            "end_utc": _iso_at(epoch, enforced_window_end_s),
        }
    ]

    problem = build_problem_from_config(cfg)
    plan = problem.build_plan(_assignment_for_target(cfg, target_id))
    sim = problem.simulate(plan, np.random.default_rng(0))
    report = evaluate_constraints(sim, problem.constraints)
    observations = [event for event in plan.schedule.events if event.etype == EventType.OBSERVATION]

    assert len(observations) == 1
    assert observations[0].t_start == pytest.approx(raw_first_window[0])
    assert observations[0].t_start < enforced_window_start_s
    assert sim.metadata["target_time_windows_enforced"] is False
    assert "target_time_windows" not in report.by_name()


def test_spacecraft_validation_rejects_unusable_enforced_target_window() -> None:
    cfg = _load_spacecraft_demo()
    cfg.setdefault("constraints", {})["enforce_target_time_windows"] = True
    cfg["mission"]["targets"][0]["time_windows"] = [
        {
            "start_utc": "2026-02-01T00:00:00Z",
            "end_utc": "2026-02-02T00:00:00Z",
        }
    ]

    issues = collect_scenario_validation_issues(cfg)
    paths = {issue.path for issue in issues}

    assert "mission.targets[0].time_windows" in paths


def test_spacecraft_validation_allows_metadata_only_target_window_outside_horizon() -> None:
    cfg = _load_spacecraft_demo()
    cfg.setdefault("constraints", {})["enforce_target_time_windows"] = False
    cfg["mission"]["targets"][0]["time_windows"] = [
        {
            "start_utc": "2026-02-01T00:00:00Z",
            "end_utc": "2026-02-02T00:00:00Z",
        }
    ]

    issues = collect_scenario_validation_issues(cfg)
    paths = {issue.path for issue in issues}

    assert "mission.targets[0].time_windows" not in paths
