from __future__ import annotations

from mission_framework.reporting.flight_output import (
    _bundle_completeness,
    _format_artifact_index,
)


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
    assert "| Artifact | Status | Link | Type |" in markdown
    assert "| Scenario YAML | included | [scenario.yaml](scenario.yaml) | expected |" in markdown
    assert "| Flight path plot | missing | flight path.png | expected |" in markdown
    assert (
        "| Evidence bundle artifact index | included | "
        "[artifact_index.md](artifact_index.md) | generated |"
    ) in markdown
