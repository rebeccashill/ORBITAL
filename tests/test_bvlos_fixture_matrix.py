from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "bvlos_fixtures"
FIXTURE_OUTPUT_DIR = ROOT / "outputs" / "bvlos_fixtures"
GENERATED_AT = "2026-09-15T05:24:50Z"
REPRESENTATIVE_OUTPUTS = (
    "manifest.json",
    "operator_dashboard.md",
    "operator_review_ui.html",
    "checksum_manifest.json",
)

FIXTURE_CASES = (
    (
        "bvlos_ready_evidence_fixture.yaml",
        "bvlos_fixture_ready_evidence",
        "ready",
    ),
    (
        "bvlos_stale_evidence_fixture.yaml",
        "bvlos_fixture_stale_evidence",
        "stale",
    ),
    (
        "bvlos_missing_artifact_fixture.yaml",
        "bvlos_fixture_missing_artifact",
        "missing",
    ),
    (
        "bvlos_modify_no_go_fixture.yaml",
        "bvlos_fixture_modify_no_go",
        "modify",
    ),
)


def _artifact_by_id(manifest: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    return next(artifact for artifact in manifest["artifacts"] if artifact["id"] == artifact_id)


def _warning_kinds(manifest: dict[str, Any]) -> set[str]:
    return {warning.get("kind", "") for warning in manifest.get("bundle_warnings", [])}


def _run_fixture(fixture_name: str, run_dir_name: str, outdir: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            str(FIXTURE_DIR / fixture_name),
            "--iterations",
            "5",
            "--restarts",
            "1",
            "--seed",
            "0",
            "--generated-at",
            GENERATED_AT,
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    manifest_path = outdir / run_dir_name / "operator_evidence_bundle" / "manifest.json"
    assert manifest_path.is_file()
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _run_fixture_outputs(fixture_name: str, outdir: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            str(FIXTURE_DIR / fixture_name),
            "--generated-at",
            GENERATED_AT,
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _representative_bytes(root: Path, run_dir_name: str) -> dict[str, bytes]:
    bundle_dir = root / run_dir_name / "operator_evidence_bundle"
    return {filename: (bundle_dir / filename).read_bytes() for filename in REPRESENTATIVE_OUTPUTS}


@pytest.mark.parametrize(("fixture_name", "run_dir_name", "expected"), FIXTURE_CASES)
def test_bvlos_fixture_matrix_generates_distinct_evidence_states(
    fixture_name: str, run_dir_name: str, expected: str, tmp_path: Path
) -> None:
    manifest = _run_fixture(fixture_name, run_dir_name, tmp_path / "runs")

    assert manifest["scenario_path"] == f"examples/bvlos_fixtures/{fixture_name}"
    assert manifest["freshness"]["generated_timestamp_utc"] == GENERATED_AT
    assert manifest["operator_review"]["review_timestamp_utc"] == GENERATED_AT
    assert manifest["regulatory_evidence_provenance"]["status"] in {
        "DOCUMENTED",
        "STALE",
    }

    warning_kinds = _warning_kinds(manifest)

    if expected == "ready":
        assert manifest["constraint_audit"]["status"] == "go"
        assert manifest["weather_evidence_readiness"]["status"] == "PACKAGED"
        assert manifest["weather_evidence_readiness"]["freshness_status"] == "packaged"
        assert manifest["regulatory_evidence_provenance"]["status"] == "DOCUMENTED"
        assert manifest["bundle_completeness"]["complete"] is True
        assert warning_kinds.isdisjoint(
            {
                "missing_artifact",
                "weather_evidence",
                "regulatory_evidence_provenance",
            }
        )
        assert _artifact_by_id(manifest, "robustness_summary")["present"] is True

    if expected == "stale":
        assert manifest["constraint_audit"]["status"] == "go"
        assert manifest["weather_evidence_readiness"]["status"] == "STALE"
        assert manifest["weather_evidence_readiness"]["mode"] == "sample"
        assert manifest["regulatory_evidence_provenance"]["status"] == "STALE"
        assert {"weather_evidence", "regulatory_evidence_provenance"} <= warning_kinds
        assert manifest["bundle_completeness"]["complete"] is True

    if expected == "missing":
        robustness = _artifact_by_id(manifest, "robustness_summary")
        assert manifest["constraint_audit"]["status"] == "go"
        assert manifest["weather_evidence_readiness"]["status"] == "PACKAGED"
        assert manifest["regulatory_evidence_provenance"]["status"] == "DOCUMENTED"
        assert manifest["bundle_completeness"]["complete"] is False
        assert robustness["present"] is False
        assert robustness["bundle_path"] == "robustness.json"
        assert "missing_artifact" in warning_kinds
        assert {
            item["id"] for item in manifest["missing_evidence"] if item["kind"] == "artifact"
        } == {"robustness_summary"}

    if expected == "modify":
        top_constraint = manifest["constraint_audit"]["top_limiting_constraint"]
        assert manifest["constraint_audit"]["status"] == "modify"
        assert top_constraint["id"] == "battery_reserve"
        assert top_constraint["status"] == "fail"
        assert top_constraint["margin"]["value"] < 0
        assert manifest["operator_review"]["requested_status"] == "ready_for_review"
        assert manifest["operator_review"]["status"] == "draft"
        assert "modify mission" in manifest["operator_review"]["operator_decision"]
        assert "missing_artifact" in warning_kinds


@pytest.mark.parametrize(("fixture_name", "run_dir_name", "expected"), FIXTURE_CASES)
def test_bvlos_fixture_representative_outputs_are_committed(
    fixture_name: str, run_dir_name: str, expected: str
) -> None:
    bundle_dir = FIXTURE_OUTPUT_DIR / run_dir_name / "operator_evidence_bundle"
    manifest_path = bundle_dir / "manifest.json"

    for filename in REPRESENTATIVE_OUTPUTS:
        assert (bundle_dir / filename).is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["scenario_path"] == f"examples/bvlos_fixtures/{fixture_name}"
    assert manifest["freshness"]["generated_timestamp_utc"] == GENERATED_AT
    assert manifest["operator_review"]["review_timestamp_utc"] == GENERATED_AT
    assert manifest["ui_manifest_version"] == 1
    assert manifest["freshness"]["command"]["display"]

    if expected == "ready":
        assert manifest["bundle_completeness"]["complete"] is True
        assert manifest["weather_evidence_readiness"]["status"] == "PACKAGED"
    if expected == "stale":
        assert manifest["weather_evidence_readiness"]["status"] == "STALE"
        assert manifest["regulatory_evidence_provenance"]["status"] == "STALE"
    if expected == "missing":
        assert manifest["bundle_completeness"]["complete"] is False
        assert _artifact_by_id(manifest, "robustness_summary")["present"] is False
    if expected == "modify":
        assert manifest["constraint_audit"]["status"] == "modify"
        assert manifest["constraint_audit"]["top_limiting_constraint"]["id"] == "battery_reserve"


@pytest.mark.parametrize(("fixture_name", "run_dir_name", "_expected"), FIXTURE_CASES)
def test_bvlos_fixture_outputs_are_stable_across_reruns(
    fixture_name: str, run_dir_name: str, _expected: str, tmp_path: Path
) -> None:
    outdir = tmp_path / "outputs" / "bvlos_fixtures"

    _run_fixture_outputs(fixture_name, outdir)
    first_outputs = _representative_bytes(outdir, run_dir_name)

    _run_fixture_outputs(fixture_name, outdir)
    second_outputs = _representative_bytes(outdir, run_dir_name)

    assert second_outputs == first_outputs
