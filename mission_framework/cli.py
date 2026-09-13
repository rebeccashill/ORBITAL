# mission_framework/cli.py
"""
CLI entry point for running an aircraft or spacecraft scenario YAML.

Usage:
    python -m mission_framework.cli examples/aircraft_uav_demo.yaml
    python -m mission_framework.cli examples/cubesat_leo_demo.yaml

What this CLI does:
- Loads YAML scenario
- Builds a Problem (domain-specific builder, unified core interfaces)
- Runs the unified Planner
- Prints summary + writes simple JSON artifacts
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml  # PyYAML

from mission_framework.core.constraints import Severity
from mission_framework.core.decision_variables import MutationConfig
from mission_framework.core.json_utils import strict_json_dumps, write_strict_json
from mission_framework.core.objective import RobustAggregation, ScoreConfig
from mission_framework.core.planner import Planner, PlannerConfig, Problem
from mission_framework.scenario_validation import (
    ScenarioValidationError,
    collect_scenario_validation_issues,
    validate_scenario_config,
)
from mission_framework.simulation.feasibility import format_feasibility_report


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _print_validation_error(path: Path, exc: Exception) -> None:
    print(f"INVALID: {path}", file=sys.stderr)
    print(str(exc), file=sys.stderr)


def _print_validation_warnings(path: Path, cfg: Any, expected_type: Optional[str] = None) -> None:
    warnings = [
        issue
        for issue in collect_scenario_validation_issues(cfg, expected_type=expected_type)
        if issue.is_warning
    ]
    if not warnings:
        return
    print(f"WARNING: {path}", file=sys.stderr)
    for warning in warnings:
        print(f"- {warning}", file=sys.stderr)


def _validate_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Validate an ORBITAL scenario YAML file.")
    ap.add_argument("scenario_yaml", type=str, help="Path to scenario YAML.")
    ap.add_argument(
        "--type",
        choices=("aircraft", "spacecraft"),
        default=None,
        help="Optionally require a specific scenario type.",
    )

    args = ap.parse_args(argv)
    scenario_path = Path(args.scenario_yaml).resolve()

    try:
        cfg = _load_yaml(scenario_path)
        if isinstance(cfg, dict):
            cfg["_scenario_dir"] = str(scenario_path.parent)
        validate_scenario_config(cfg, expected_type=args.type)
        _print_validation_warnings(scenario_path, cfg, expected_type=args.type)
    except (OSError, yaml.YAMLError, ScenarioValidationError) as exc:
        _print_validation_error(scenario_path, exc)
        return 2

    scenario = cfg.get("scenario", {}) if isinstance(cfg, dict) else {}
    print(f"VALID: {scenario_path}")
    print(f"Scenario: {scenario.get('name', '(unnamed)')}")
    print(f"Type: {scenario.get('type', '(unknown)')}")
    return 0


def _planner_config_from_yaml(cfg: Dict[str, Any]) -> PlannerConfig:
    p = cfg.get("planner", {}) or {}
    mut = p.get("mutation", {}) or {}

    # Scoring config (unified with core/objective.py)
    scoring = ScoreConfig(
        penalty_weight=float(p.get("penalty_weight", 1000.0)),
        include_hard=True,
        include_soft=True,
        margin_reward_weight=float(p.get("margin_reward_weight", 0.0)),
        robust_aggregation=RobustAggregation.MEAN,  # overridden in Problem when robustness is enabled
        cvar_alpha=float(p.get("cvar_alpha", 0.8)),
    )

    return PlannerConfig(
        iterations=int(p.get("iterations", 2000)),
        restarts=int(p.get("restarts", 5)),
        scoring=scoring,
        hard_infeasible_penalty=float(p.get("hard_infeasible_penalty", 1e6)),
        seed=int(p.get("seed", 0)),
        keep_history=bool(cfg.get("output", {}).get("save_history", True)),
        history_stride=int(p.get("history_stride", 1)),
        mutation=MutationConfig(
            cont_sigma=float(mut.get("cont_sigma", 0.10)),
            cont_sigma_is_frac=bool(mut.get("cont_sigma_is_frac", True)),
            int_step=int(mut.get("int_step", 1)),
            p_flip=float(mut.get("p_flip", 0.05)),
            p_perm_swap=float(mut.get("p_perm_swap", 0.50)),
            perm_swaps=int(mut.get("perm_swaps", 2)),
        ),
    )


def _build_problem(cfg: Dict[str, Any]) -> Problem:
    scenario = cfg.get("scenario", {}) or {}
    stype = (scenario.get("type") or "").strip().lower()

    if stype == "aircraft":
        from mission_framework.aircraft.mission import build_problem_from_config

        return build_problem_from_config(cfg)

    if stype == "spacecraft":
        from mission_framework.spacecraft.mission import build_problem_from_config

        return build_problem_from_config(cfg)

    raise ValueError(f"Unknown scenario.type '{stype}'. Expected 'aircraft' or 'spacecraft'.")


def _write_json(out_path: Path, obj: Any) -> None:
    write_strict_json(out_path, obj)


def _run_single_scenario(argv: Sequence[str]) -> int:
    return main(argv)


def _scenario_output_dir(scenario_path: Path, outdir: Path) -> Path:
    cfg = _load_yaml(scenario_path)
    output_cfg = cfg.get("output", {}) if isinstance(cfg, dict) else {}
    run_dir_name = str(output_cfg.get("run_dir_name") or scenario_path.stem).strip()
    return outdir.resolve() / run_dir_name


def _read_json_mapping(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_bundle_dir(bundle_path: str) -> Path:
    path = Path(bundle_path).resolve()
    if path.is_file():
        return path.parent
    return path


def _load_bundle_manifest(bundle_path: str) -> tuple[Path, Dict[str, Any]]:
    bundle_dir = _resolve_bundle_dir(bundle_path)
    manifest = _read_json_mapping(bundle_dir / "manifest.json")
    if not manifest:
        raise FileNotFoundError(
            f"Evidence bundle manifest not found: {bundle_dir / 'manifest.json'}"
        )
    return bundle_dir, manifest


def _bundle_open_first_path(bundle_dir: Path, manifest: Dict[str, Any]) -> Path:
    for candidate in (
        "operator_dashboard.md",
        "evidence_bundle_summary.md",
        "artifact_index.md",
        "inspection_constraint_audit.md",
    ):
        path = bundle_dir / candidate
        if path.exists():
            return path
    for entry in manifest.get("generated_artifacts", []) or []:
        if entry.get("present") and entry.get("bundle_path"):
            return bundle_dir / str(entry["bundle_path"])
    return bundle_dir / "manifest.json"


def _format_cli_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "not provided"
    if isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, (int, float)):
        text = f"{float(value):.1f}"
    else:
        text = str(value)
    return f"{text} {unit}".strip() if unit else text


def _format_constraint_status(value: Any) -> str:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
    labels = {
        "pass": "PASS",
        "passed": "PASS",
        "warning": "WARNING",
        "review": "WARNING",
        "review_required": "WARNING",
        "fail": "FAIL",
        "failed": "FAIL",
        "unknown": "UNKNOWN",
    }
    return labels.get(normalized, normalized.upper() if normalized else "UNKNOWN")


def _format_top_constraint(top: Dict[str, Any]) -> str:
    margin = top.get("margin") or {}
    label = top.get("label") or "not available"
    status = _format_constraint_status(top.get("status"))
    margin_text = _format_cli_value(margin.get("value"), str(margin.get("unit") or ""))
    return f"{label}: {status}, margin {margin_text}"


def _artifact_present(manifest: Dict[str, Any], artifact_id: str) -> bool:
    return any(
        entry.get("id") == artifact_id and bool(entry.get("present"))
        for entry in manifest.get("artifacts", []) or []
    )


def _bundle_summary_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Summarize an existing ORBITAL evidence bundle.")
    ap.add_argument("bundle", help="Evidence bundle directory or manifest.json path.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(list(argv))

    try:
        bundle_dir, manifest = _load_bundle_manifest(args.bundle)
    except FileNotFoundError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    audit = manifest.get("constraint_audit") or {}
    top = audit.get("top_limiting_constraint") or {}
    readiness = manifest.get("regulatory_readiness") or {}
    bundle_completeness = (
        manifest.get("artifact_completeness") or manifest.get("bundle_completeness") or {}
    )
    regulatory_completeness = manifest.get("regulatory_documentation_completeness") or {}
    review = manifest.get("operator_review") or {}
    missing = manifest.get("missing_evidence") or []
    warnings = manifest.get("bundle_warnings") or []
    open_first = _bundle_open_first_path(bundle_dir, manifest)

    payload = {
        "bundle_dir": str(bundle_dir),
        "open_first": str(open_first),
        "mission_id": audit.get("mission_id"),
        "mission_status": audit.get("status"),
        "mission_risk": audit.get("mission_risk"),
        "top_limiting_constraint": top,
        "regulatory_readiness": readiness,
        "artifact_completeness_score": bundle_completeness.get("score"),
        "regulatory_documentation_completeness_score": regulatory_completeness.get("score"),
        "operator_review_status": review.get("status"),
        "bundle_warning_count": len(warnings),
        "missing_evidence_count": len(missing),
    }
    if args.json:
        print(strict_json_dumps(payload, indent=2))
        return 0

    print("=== ORBITAL Evidence Bundle Summary ===")
    print(f"Bundle: {bundle_dir}")
    print(f"Open first: {open_first}")
    print(f"Mission: {payload['mission_id'] or 'not provided'}")
    print(f"Mission status: {str(payload['mission_status'] or 'unknown').upper()}")
    print(f"Mission risk: {str(payload['mission_risk'] or 'unknown').upper()}")
    print(f"Top limiting constraint: {_format_top_constraint(top)}")
    print(
        "Regulatory readiness: "
        f"{str(readiness.get('readiness_state') or readiness.get('status') or 'unknown').upper()}"
    )
    print(
        "Artifact completeness: "
        f"{_format_cli_value(payload['artifact_completeness_score'], '%')}"
    )
    print(
        "Regulatory documentation completeness: "
        f"{_format_cli_value(payload['regulatory_documentation_completeness_score'], '%')}"
    )
    print(f"Operator review status: {review.get('status') or 'not provided'}")
    print(f"Bundle warnings: {len(warnings)}")
    print(f"Missing evidence items: {len(missing)}")
    return 0


def _bundle_verify_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Verify ORBITAL evidence bundle checksums.")
    ap.add_argument("bundle", help="Evidence bundle directory or manifest.json path.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(list(argv))

    bundle_dir = _resolve_bundle_dir(args.bundle)
    try:
        from mission_framework.reporting.flight_output import verify_evidence_bundle_checksums

        result = verify_evidence_bundle_checksums(bundle_dir)
    except Exception as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(strict_json_dumps(result, indent=2))
    else:
        print("=== ORBITAL Evidence Bundle Checksum Verification ===")
        print(f"Bundle: {bundle_dir}")
        print(f"Status: {'OK' if result.get('ok') else 'FAILED'}")
        print(f"Checksum OK: {'yes' if result.get('checksum_ok') else 'no'}")
        print(f"Scenario metadata OK: {'yes' if result.get('scenario_metadata_ok') else 'no'}")
        print(f"Checked files: {result.get('checked_files', 0)}")
        warnings = result.get("warnings") or []
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- {warning.get('id') or warning.get('kind')}: {warning.get('message')}")
    return 0 if result.get("ok") else 1


def _bundle_top_constraint_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Print the top limiting constraint and recommended operator action."
    )
    ap.add_argument("bundle", help="Evidence bundle directory or manifest.json path.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(list(argv))

    try:
        bundle_dir, manifest = _load_bundle_manifest(args.bundle)
    except FileNotFoundError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    audit = _read_json_mapping(bundle_dir / "inspection_constraint_audit.json")
    manifest_audit = manifest.get("constraint_audit") or {}
    top = (
        audit.get("top_limiting_constraint") or manifest_audit.get("top_limiting_constraint") or {}
    )
    if not top:
        print("No top limiting constraint found in bundle.", file=sys.stderr)
        return 1
    transparency = audit.get("model_transparency") or {}
    selection = (
        transparency.get("top_limiting_constraint_selection")
        or audit.get("top_limiting_constraint_selection")
        or {}
    )
    payload = {
        "bundle_dir": str(bundle_dir),
        "top_limiting_constraint": top,
        "recommended_operator_action": top.get("recommended_operator_action")
        or top.get("recommendation"),
        "selection_rationale": selection.get("explanation"),
    }
    if args.json:
        print(strict_json_dumps(payload, indent=2))
        return 0

    print("=== ORBITAL Top Limiting Constraint ===")
    print(f"Bundle: {bundle_dir}")
    print(_format_top_constraint(top))
    print("Why this matters: " f"{top.get('why_this_matters_to_operator') or 'not provided'}")
    print(
        "Recommended operator action: "
        f"{payload['recommended_operator_action'] or 'not provided'}"
    )
    if payload["selection_rationale"]:
        print(f"Selection detail: {payload['selection_rationale']}")
    return 0


def _parse_review_timestamp(value: Any) -> bool:
    if value is None or value == "":
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _bundle_review_validate_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Validate evidence bundle review metadata without rerunning optimization."
    )
    ap.add_argument("bundle", help="Evidence bundle directory or manifest.json path.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(list(argv))

    try:
        bundle_dir, manifest = _load_bundle_manifest(args.bundle)
    except FileNotFoundError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    review = manifest.get("operator_review") or {}
    review_metadata = manifest.get("review_metadata") or {}
    status = review.get("status") or review_metadata.get("status")
    allowed = set(review.get("allowed_statuses") or ["draft", "ready_for_review", "reviewed"])
    errors: list[Dict[str, Any]] = []
    warnings: list[Dict[str, Any]] = []

    if status not in allowed:
        errors.append(
            {
                "path": "operator_review.status",
                "message": f"status must be one of: {', '.join(sorted(allowed))}",
            }
        )
    if (
        review_metadata.get("status")
        and review.get("status")
        and review_metadata.get("status") != review.get("status")
    ):
        errors.append(
            {
                "path": "review_metadata.status",
                "message": "review_metadata.status does not match operator_review.status",
            }
        )
    if not _parse_review_timestamp(review.get("review_timestamp_utc")):
        errors.append(
            {
                "path": "operator_review.review_timestamp_utc",
                "message": "review timestamp must be ISO-8601 when provided",
            }
        )
    for key in ("reviewer_name", "review_notes", "operator_decision"):
        value = review.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(
                {
                    "path": f"operator_review.{key}",
                    "message": "must be a non-empty string when provided",
                }
            )
    if status == "reviewed" and not review.get("reviewer_name"):
        warnings.append(
            {
                "path": "operator_review.reviewer_name",
                "message": "reviewed bundles should document reviewer_name",
            }
        )
    if status == "reviewed" and not review.get("review_timestamp_utc"):
        warnings.append(
            {
                "path": "operator_review.review_timestamp_utc",
                "message": "reviewed bundles should document review_timestamp_utc",
            }
        )
    if manifest.get("bundle_warnings") and status in {"ready_for_review", "reviewed"}:
        warnings.append(
            {
                "path": "bundle_warnings",
                "message": "bundle has warnings; review status may need attention",
            }
        )
    if manifest.get("missing_evidence") and status in {"ready_for_review", "reviewed"}:
        warnings.append(
            {
                "path": "missing_evidence",
                "message": "bundle has missing evidence; review status may need attention",
            }
        )

    payload = {
        "bundle_dir": str(bundle_dir),
        "valid": not errors,
        "status": status,
        "documentation_only": bool(review.get("documentation_only", True)),
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(strict_json_dumps(payload, indent=2))
        return 0 if payload["valid"] else 1

    print("=== ORBITAL Review Metadata Validation ===")
    print(f"Bundle: {bundle_dir}")
    print(f"Review metadata: {'VALID' if payload['valid'] else 'INVALID'}")
    print(f"Operator review status: {status or 'not provided'}")
    print("Documentation-only: yes")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error['path']}: {error['message']}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning['path']}: {warning['message']}")
    return 0 if payload["valid"] else 1


BUNDLE_COMMANDS = {
    "bundle-summary": _bundle_summary_command,
    "evidence-summary": _bundle_summary_command,
    "bundle-verify": _bundle_verify_command,
    "verify-bundle": _bundle_verify_command,
    "bundle-top": _bundle_top_constraint_command,
    "top-constraint": _bundle_top_constraint_command,
    "bundle-review-validate": _bundle_review_validate_command,
    "review-validate": _bundle_review_validate_command,
}


def _first_artifact_to_open(outdir: Path, scenario_type: str) -> Optional[Path]:
    candidates: list[Path]
    if scenario_type == "aircraft":
        candidates = [
            outdir / "operator_evidence_bundle" / "operator_dashboard.md",
            outdir / "inspection_constraint_audit.md",
            outdir / "regulatory_readiness_report.md",
            outdir / "operator_memo.md",
        ]
    elif scenario_type == "spacecraft":
        candidates = [
            outdir / "mission_timeline.png",
            outdir / "operations_summary.png",
            outdir / "schedule.csv",
            outdir / "plan.json",
        ]
    else:
        candidates = [outdir / "plan.json"]
    return next((path for path in candidates if path.exists()), None)


def _batch_summary_row(scenario_path: Path, outdir: Path, exit_code: int) -> Dict[str, Any]:
    cfg = _load_yaml(scenario_path)
    scenario = cfg.get("scenario", {}) if isinstance(cfg, dict) else {}
    run_dir = _scenario_output_dir(scenario_path, outdir)
    audit = _read_json_mapping(run_dir / "inspection_constraint_audit.json")
    top = audit.get("top_limiting_constraint") if isinstance(audit, dict) else {}
    top = top if isinstance(top, dict) else {}
    evidence_dir = run_dir / "operator_evidence_bundle"

    return {
        "scenario": str(scenario_path),
        "mission": scenario.get("name", scenario_path.stem),
        "exit_code": exit_code,
        "status": audit.get("status") or ("error" if exit_code else "complete"),
        "risk": audit.get("mission_risk") or "unknown",
        "top_constraint": top.get("label") or "not available",
        "top_constraint_status": top.get("status") or "unknown",
        "evidence_path": str(evidence_dir) if evidence_dir.exists() else "",
        "output_path": str(run_dir),
    }


def _write_batch_summary(rows: Sequence[Dict[str, Any]], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    fields = [
        "scenario",
        "mission",
        "exit_code",
        "status",
        "risk",
        "top_constraint",
        "top_constraint_status",
        "evidence_path",
        "output_path",
    ]
    with (outdir / "batch_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    lines = [
        "# ORBITAL Batch Summary",
        "",
        "| Mission | Status | Risk | Top Constraint | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        top_constraint = (
            f"{row.get('top_constraint', 'not available')} "
            f"({row.get('top_constraint_status', 'unknown')})"
        )
        lines.append(
            "| {mission} | {status} | {risk} | {top} | {evidence} |".format(
                mission=row.get("mission", ""),
                status=row.get("status", ""),
                risk=row.get("risk", ""),
                top=top_constraint,
                evidence=row.get("evidence_path", ""),
            )
        )
    (outdir / "batch_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _batch_command(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Run multiple ORBITAL scenarios and summarize them.")
    ap.add_argument("scenario_yamls", nargs="+", help="Scenario YAML files to run.")
    ap.add_argument("--outdir", type=str, default="batch_runs", help="Batch output directory.")
    ap.add_argument("--iterations", type=int, default=None, help="Override planner.iterations")
    ap.add_argument("--restarts", type=int, default=None, help="Override planner.restarts")
    ap.add_argument("--robustness", type=int, default=None, help="Override robustness.cases")
    ap.add_argument("--seed", type=int, default=None, help="Override planner seed")
    ap.add_argument("--no-plots", action="store_true", help="Skip PNG plot generation")
    args = ap.parse_args(list(argv))

    outdir = Path(args.outdir).resolve()
    rows: list[Dict[str, Any]] = []
    for scenario_yaml in args.scenario_yamls:
        scenario_path = Path(scenario_yaml).resolve()
        run_args = [str(scenario_path), "--outdir", str(outdir)]
        if args.iterations is not None:
            run_args.extend(["--iterations", str(args.iterations)])
        if args.restarts is not None:
            run_args.extend(["--restarts", str(args.restarts)])
        if args.robustness is not None:
            run_args.extend(["--robustness", str(args.robustness)])
        if args.seed is not None:
            run_args.extend(["--seed", str(args.seed)])
        if args.no_plots:
            run_args.append("--no-plots")

        exit_code = _run_single_scenario(run_args)
        rows.append(_batch_summary_row(scenario_path, outdir, exit_code))

    _write_batch_summary(rows, outdir)
    print(f"\nWrote batch summary to: {outdir}")
    return 0 if all(int(row.get("exit_code", 1)) == 0 for row in rows) else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "validate":
        return _validate_command(raw_args[1:])
    if raw_args and raw_args[0] == "batch":
        return _batch_command(raw_args[1:])
    if raw_args and raw_args[0] in BUNDLE_COMMANDS:
        return BUNDLE_COMMANDS[raw_args[0]](raw_args[1:])

    ap = argparse.ArgumentParser(description="Run ORBITAL unified mission planning scenarios.")
    ap.add_argument(
        "scenario_yaml", type=str, help="Path to scenario YAML (aircraft or spacecraft)."
    )
    ap.add_argument(
        "--outdir", type=str, default="runs", help="Output directory for reports/artifacts."
    )
    ap.add_argument(
        "-outdir",
        dest="outdir",
        type=str,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--iterations", type=int, default=None, help="Override planner.iterations")
    ap.add_argument(
        "-iterations",
        dest="iterations",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--restarts", type=int, default=None, help="Override planner.restarts")
    ap.add_argument(
        "-restarts",
        dest="restarts",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--robustness", type=int, default=None, help="Override robustness.cases")
    ap.add_argument(
        "-robustness",
        dest="robustness",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducible runs")
    ap.add_argument(
        "-seed",
        dest="seed",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--no-plots", action="store_true", help="Skip PNG plot generation")
    ap.add_argument(
        "-no-plots",
        dest="no_plots",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    args = ap.parse_args(raw_args)
    if args.seed is not None:
        import random

        random.seed(args.seed)
        try:
            import numpy as np

            np.random.seed(args.seed)
        except Exception:
            pass

    scenario_path = Path(args.scenario_yaml).resolve()
    try:
        cfg = _load_yaml(scenario_path)
        if isinstance(cfg, dict):
            cfg["_scenario_dir"] = str(scenario_path.parent)
    except (OSError, yaml.YAMLError) as exc:
        _print_validation_error(scenario_path, exc)
        return 2

    # Optional overrides for fast runs
    if args.iterations is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["iterations"] = int(args.iterations)

    if args.restarts is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["restarts"] = int(args.restarts)

    if args.robustness is not None:
        cfg.setdefault("robustness", {})
        cfg["robustness"]["cases"] = int(args.robustness)

    if args.seed is not None:
        cfg.setdefault("planner", {})
        cfg["planner"]["seed"] = int(args.seed)

    try:
        validate_scenario_config(cfg)
        _print_validation_warnings(scenario_path, cfg)
    except ScenarioValidationError as exc:
        _print_validation_error(scenario_path, exc)
        return 2

    generate_plots = not bool(args.no_plots)

    # Build problem
    problem = _build_problem(cfg)

    # Attach robustness settings (planner uses Problem.robustness_cases/seeds)
    rob = cfg.get("robustness", {}) or {}
    problem.robustness_cases = int(rob.get("cases", 0)) if rob else 0

    # Optional robust aggregation settings from YAML.
    # Example:
    # robustness:
    #   cases: 50
    #   aggregation: cvar
    #   cvar_alpha: 0.8
    agg = (rob.get("aggregation") or "").strip().lower()
    if agg in ("mean", "worst", "cvar"):
        problem.robust_aggregation = RobustAggregation(agg)
    if "cvar_alpha" in rob:
        problem.cvar_alpha = float(rob["cvar_alpha"])

    # Planner
    planner_cfg = _planner_config_from_yaml(cfg)
    planner = Planner(planner_cfg)

    # Solve
    result = planner.solve(problem)

    # Console summary
    print("\n=== ORBITAL: Planning Complete ===")
    print(f"Scenario: {cfg.get('scenario', {}).get('name', '(unnamed)')}")
    print(f"Type:     {cfg.get('scenario', {}).get('type', '(unknown)')}")
    print(f"Score:    {result.score:.6g}")
    print(f"Feasible: {result.constraints.hard_pass}")

    worst_hard = result.constraints.worst(Severity.HARD)
    if worst_hard is not None:
        print(f"Worst HARD margin: {worst_hard.min_margin:+.6g} ({worst_hard.name})")

    print("\n--- Constraint Report (top worst first) ---")
    print(format_feasibility_report(result.constraints, max_lines=40))

    print("\n--- Score Breakdown ---")
    print(strict_json_dumps(result.score_report.to_jsonable(), indent=2))

    if result.robustness is not None:
        print("\n--- Robustness Summary ---")
        print(strict_json_dumps(result.robustness, indent=2))

    # Write basic artifacts
    output_cfg = cfg.get("output", {}) or {}
    run_dir_name = str(output_cfg.get("run_dir_name") or scenario_path.stem).strip()
    outdir = Path(args.outdir).resolve() / run_dir_name
    outdir.mkdir(parents=True, exist_ok=True)

    scenario_type = str(cfg.get("scenario", {}).get("type", "")).strip().lower()
    command_argv = [sys.executable, "-m", "mission_framework.cli", *raw_args]
    command_used = {
        "argv": command_argv,
        "display": subprocess.list2cmdline(command_argv),
    }

    if scenario_type == "aircraft":
        # Optional human-readable output
        try:
            from mission_framework.reporting.flight_output import (
                export_inspection_constraint_audit,
                export_operator_memo,
                export_regulatory_readiness_report,
                export_waypoints_csv,
                export_what_if_plan,
                print_flight_plan,
            )

            print("\n--- Flight Plan ---")
            print(print_flight_plan(result.plan))
            export_waypoints_csv(result.plan, outdir / "waypoints.csv")
            export_operator_memo(
                result.plan,
                result.sim_result,
                result.constraints,
                result.score_report,
                outdir / "operator_memo.md",
                robustness=result.robustness,
                cfg=cfg,
            )
            export_inspection_constraint_audit(
                result.plan,
                result.sim_result,
                result.constraints,
                outdir,
                cfg=cfg,
                robustness=result.robustness,
                scenario_path=scenario_path,
                command_used=command_used,
            )
            export_regulatory_readiness_report(
                result.plan,
                result.sim_result,
                result.constraints,
                outdir,
                cfg=cfg,
                robustness=result.robustness,
            )
            if bool(output_cfg.get("export_what_if_plan", False)):
                export_what_if_plan(
                    result.plan,
                    result.sim_result,
                    result.constraints,
                    result.score_report,
                    outdir,
                    cfg=cfg,
                    robustness=result.robustness,
                )
        except Exception as e:
            print(f"(flight reporting skipped: {e})")

        if generate_plots:
            try:
                from mission_framework.visualization.aircraft_plots import plot_aircraft_mission

                mission_name = cfg.get("scenario", {}).get("name", "Aircraft Mission")
                plot_files = plot_aircraft_mission(
                    result.plan, result.sim_result, outdir, mission_name
                )
                if plot_files:
                    print("\n--- Plots Generated ---")
                    for plot_name, plot_path in plot_files.items():
                        print(f"  {plot_name}: {plot_path.name}")
            except Exception as e:
                print(f"(plot generation skipped: {e})")

    elif scenario_type == "spacecraft":
        try:
            from mission_framework.reporting.schedule_output import (
                export_schedule_csv,
                print_schedule,
            )

            print("\n--- 7-Day Schedule ---")
            print(print_schedule(result.plan))
            export_schedule_csv(result.plan, outdir / "schedule.csv")
        except Exception as e:
            print(f"(schedule reporting skipped: {e})")

        if generate_plots:
            try:
                from mission_framework.visualization.spacecraft_plots import plot_spacecraft_mission

                mission_name = cfg.get("scenario", {}).get("name", "Spacecraft Mission")
                plot_files = plot_spacecraft_mission(
                    result.plan, result.sim_result, outdir, mission_name
                )
                if plot_files:
                    print("\n--- Plots Generated ---")
                    for plot_name, plot_path in plot_files.items():
                        print(f"  {plot_name}: {plot_path.name}")
            except Exception as e:
                print(f"(plot generation skipped: {e})")

    # Core JSON artifacts for repeatable reporting.
    _write_json(outdir / "score.json", result.score_report.to_jsonable())
    _write_json(
        outdir / "constraints.json",
        (
            result.constraints.to_jsonable()
            if hasattr(result.constraints, "to_jsonable")
            else result.constraints.summary()
        ),
    )
    if result.robustness is not None:
        _write_json(outdir / "robustness.json", result.robustness)
    weather_metadata = (cfg.get("weather", {}) or {}).get("resolved", {}) or {}
    if scenario_type == "aircraft" and weather_metadata:
        _write_json(outdir / "weather.json", weather_metadata)

    # Minimal generic plan export
    plan_payload: Dict[str, Any] = {
        "kind": getattr(result.plan, "kind", None),
        "metadata": getattr(result.plan, "metadata", {}),
        "waypoints": getattr(result.plan, "waypoints", None),
        "schedule": None,
    }
    sched = getattr(result.plan, "schedule", None)
    if sched is not None:
        plan_payload["schedule"] = [
            {
                "t_start": getattr(e, "t_start", None),
                "t_end": getattr(e, "t_end", None),
                "etype": str(getattr(e, "etype", None)),
                "label": getattr(e, "label", None),
                "target_id": getattr(e, "target_id", None),
                "location": getattr(e, "location", None),
                "data": getattr(e, "data", None),
            }
            for e in getattr(sched, "events", [])
        ]

    _write_json(outdir / "plan.json", plan_payload)

    # History (if enabled)
    if result.history is not None:
        _write_json(outdir / "history.json", result.history)

    flight_exports_enabled = bool(
        output_cfg.get("export_flight_planning_exports", False)
        or output_cfg.get("export_autopilot_csv", False)
        or output_cfg.get("export_kml", False)
    )
    if scenario_type == "aircraft" and flight_exports_enabled:
        try:
            from mission_framework.reporting.flight_output import export_flight_planning_artifacts

            export_flight_planning_artifacts(
                result.plan,
                outdir,
                cfg=cfg,
                export_csv=bool(output_cfg.get("export_autopilot_csv", True)),
                export_kml=bool(output_cfg.get("export_kml", True)),
            )
        except Exception as e:
            print(f"(flight-planning exports skipped: {e})")

    if scenario_type == "aircraft" and bool(
        output_cfg.get("export_operator_evidence_bundle", False)
    ):
        try:
            from mission_framework.reporting.flight_output import export_operator_evidence_bundle

            export_operator_evidence_bundle(
                outdir,
                scenario_path,
                cfg=cfg,
                command_used=command_used,
            )
        except Exception as e:
            print(f"(operator evidence bundle skipped: {e})")

    print(f"\nWrote outputs to: {outdir}")
    first_artifact = _first_artifact_to_open(outdir, scenario_type)
    if first_artifact is not None:
        print(f"Open first: {first_artifact}")
    artifact_index = outdir / "operator_evidence_bundle" / "artifact_index.md"
    if artifact_index.exists():
        print(f"Artifact index: {artifact_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
