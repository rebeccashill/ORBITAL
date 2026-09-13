from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from run_all import build_cli_cmd

ROOT = Path(__file__).resolve().parents[1]


def test_run_all_builds_supported_no_plots_commands() -> None:
    cmd = build_cli_cmd(
        python=sys.executable,
        yaml_path="examples/aircraft_uav_demo.yaml",
        iterations=5,
        restarts=1,
        robustness=0,
        seed=3,
        extra_args=["--no-plots"],
    )

    assert cmd[:3] == [sys.executable, "-m", "mission_framework.cli"]
    assert "--no-plots" in cmd
    assert cmd[cmd.index("--iterations") + 1] == "5"
    assert cmd[cmd.index("--seed") + 1] == "3"


def test_cli_no_plots_writes_core_artifacts_without_pngs(tmp_path: Path) -> None:
    outdir = tmp_path / "runs"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "examples/aircraft_uav_demo.yaml",
            "--iterations",
            "5",
            "--restarts",
            "1",
            "--robustness",
            "0",
            "--seed",
            "0",
            "--no-plots",
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    scenario_dir = outdir / "aircraft_uav_demo"
    assert (scenario_dir / "score.json").is_file()
    assert (scenario_dir / "constraints.json").is_file()
    assert (scenario_dir / "plan.json").is_file()
    assert (scenario_dir / "waypoints.csv").is_file()
    assert (scenario_dir / "regulatory_readiness_report.json").is_file()
    assert (scenario_dir / "regulatory_readiness_report.md").is_file()
    assert not list(scenario_dir.glob("*.png"))


def test_cli_seed_reproducibly_writes_same_artifacts(tmp_path: Path) -> None:
    output_roots = [tmp_path / "seed_a", tmp_path / "seed_b"]

    for outdir in output_roots:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mission_framework.cli",
                "examples/aircraft_uav_demo.yaml",
                "--iterations",
                "10",
                "--restarts",
                "1",
                "--robustness",
                "0",
                "--seed",
                "123",
                "--no-plots",
                "--outdir",
                str(outdir),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    first = output_roots[0] / "aircraft_uav_demo"
    second = output_roots[1] / "aircraft_uav_demo"
    for artifact in (
        "score.json",
        "constraints.json",
        "plan.json",
        "waypoints.csv",
        "regulatory_readiness_report.json",
        "regulatory_readiness_report.md",
    ):
        assert (first / artifact).read_bytes() == (second / artifact).read_bytes()


def test_cli_bvlos_demo_writes_full_evidence_workflow_artifacts(tmp_path: Path) -> None:
    outdir = tmp_path / "runs"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "examples/bvlos_powerline_inspection_demo.yaml",
            "--iterations",
            "5",
            "--restarts",
            "1",
            "--robustness",
            "0",
            "--seed",
            "0",
            "--no-plots",
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Open first artifact:" in result.stdout
    assert "operator_dashboard.md" in result.stdout
    assert "Local review UI:" in result.stdout
    assert "First review page: operator_review_ui.html" in result.stdout
    assert "Launch review UI:" in result.stdout
    assert "serve-ui" in result.stdout

    scenario_dir = outdir / "bvlos_powerline_inspection"
    plan_json = scenario_dir / "plan.json"
    score_json = scenario_dir / "score.json"
    constraints_json = scenario_dir / "constraints.json"
    audit_json = scenario_dir / "inspection_constraint_audit.json"
    audit_md = scenario_dir / "inspection_constraint_audit.md"
    what_if_json = scenario_dir / "what_if_plan.json"
    what_if_md = scenario_dir / "what_if_plan.md"
    report_json = scenario_dir / "regulatory_readiness_report.json"
    report_md = scenario_dir / "regulatory_readiness_report.md"
    bundle_dir = scenario_dir / "operator_evidence_bundle"
    manifest_json = bundle_dir / "manifest.json"
    bundle_readme = bundle_dir / "README.md"
    operator_review_ui = bundle_dir / "operator_review_ui.html"
    operator_dashboard = bundle_dir / "operator_dashboard.md"
    bundle_summary = bundle_dir / "evidence_bundle_summary.md"
    artifact_index = bundle_dir / "artifact_index.md"
    checksum_manifest = bundle_dir / "checksum_manifest.json"
    assert plan_json.is_file()
    assert score_json.is_file()
    assert constraints_json.is_file()
    assert audit_json.is_file()
    assert audit_md.is_file()
    assert what_if_json.is_file()
    assert what_if_md.is_file()
    assert report_json.is_file()
    assert report_md.is_file()
    assert manifest_json.is_file()
    assert bundle_readme.is_file()
    assert operator_review_ui.is_file()
    assert operator_dashboard.is_file()
    assert bundle_summary.is_file()
    assert artifact_index.is_file()
    assert checksum_manifest.is_file()

    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    assert plan["kind"] == "aircraft"
    assert plan["waypoints"]

    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["kind"] == "drone_inspection_constraint_audit"
    assert audit["primary_demo_artifact"] is True
    assert audit["operator_question"] == "Can we safely and defensibly fly this mission?"
    assert audit["top_limiting_constraint"]["label"]
    transparency = audit["model_transparency"]
    reproducibility = transparency["reproducibility"]
    assert (
        reproducibility["scenario_path"]
        .replace("\\", "/")
        .endswith("examples/bvlos_powerline_inspection_demo.yaml")
    )
    assert reproducibility["seed"] == 0
    assert reproducibility["iterations"] == 5
    assert reproducibility["robustness_cases_configured"] == 0
    assert reproducibility["robustness_cases_run"] == 0
    assert "mission_framework.cli" in reproducibility["command"]["display"]
    assert transparency["top_limiting_constraint_selection"]["selected_constraint_id"] == (
        audit["top_limiting_constraint"]["id"]
    )
    assert {item["id"] for item in transparency["assumptions_report"]} >= {
        "battery",
        "wind",
        "geofence",
        "route_completion",
        "turn_feasibility",
        "robustness",
    }
    assert audit["constraint_groups"]
    audit_markdown = audit_md.read_text(encoding="utf-8")
    assert "Operator Handoff" in audit_markdown
    assert "Plain-English Constraint Guide" in audit_markdown
    assert "Constraint Group Summary" in audit_markdown
    assert "Plain-English read:" in audit_markdown
    assert "Operator action:" in audit_markdown
    assert "Detailed Operator Review" in audit_markdown
    assert "Observed evidence:" in audit_markdown
    assert "Model Transparency" in audit_markdown
    assert "Scenario path:" in audit_markdown
    assert "mission_framework.cli" in audit_markdown

    what_if = json.loads(what_if_json.read_text(encoding="utf-8"))
    assert what_if["kind"] == "drone_inspection_what_if_plan"
    assert what_if["baseline"]["id"] == "baseline"
    assert what_if["baseline"]["feasible"] is True
    assert what_if["variants"]
    what_if_markdown = what_if_md.read_text(encoding="utf-8")
    assert "Baseline" in what_if_markdown
    assert "| Scenario | What changed | Risk | Feasible |" in what_if_markdown
    assert "Changed time" in what_if_markdown

    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["kind"] == "regulatory_readiness_report"
    assert report["not_legal_approval"] is True
    assert (
        report["regulatory_evidence"]["authorization_id"] == "example authorization reference only"
    )
    checklist_ids = {item["id"] for item in report["operator_approval_checklist"]}
    assert {
        "laanc_confirmation",
        "waiver_authorization_confirmation",
        "visual_observer_assignment",
    } <= checklist_ids

    markdown = report_md.read_text(encoding="utf-8")
    assert "Regulatory Readiness Report" in markdown
    assert "example authorization reference only" in markdown
    assert "not legal approval" in markdown.lower()

    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    artifact_presence = {artifact["id"]: artifact["present"] for artifact in manifest["artifacts"]}
    assert artifact_presence["plan_json"] is True
    assert artifact_presence["constraint_audit_markdown"] is True
    assert artifact_presence["constraint_audit_json"] is True
    assert artifact_presence["regulatory_readiness_json"] is True
    assert artifact_presence["regulatory_readiness_markdown"] is True
    assert artifact_presence["what_if_plan_markdown"] is True
    assert artifact_presence["what_if_plan_json"] is True
    assert artifact_presence["score_breakdown"] is True
    assert manifest["constraint_audit"]["status"] == "go"
    assert manifest["constraint_audit"]["mission_risk"] in {"low", "medium", "high"}
    assert manifest["constraint_audit"]["top_limiting_constraint"]["label"]
    assert manifest["regulatory_readiness"]["readiness_state"] == "operator_action_required"
    assert manifest["artifact_completeness"]["score"] == manifest["bundle_completeness_score"]
    assert manifest["regulatory_documentation_completeness"]["score"] == 100.0
    assert manifest["review_metadata"]["status"] == "draft"
    assert manifest["freshness"]["generated_timestamp_utc"].endswith("Z")
    assert manifest["freshness"]["orbital_version"] != "unknown"
    assert len(manifest["freshness"]["scenario_hash"]["value"]) == 64
    assert "mission_framework.cli" in manifest["freshness"]["command"]["display"]
    assert manifest["regulatory_metadata"]["laanc_required"] is True
    assert manifest["approval_checklist"]["item_count"] >= 8
    assert manifest["regulatory_evidence_status"]["missing"] == []
    assert 0.0 < manifest["bundle_completeness_score"] < 100.0
    assert manifest["operator_review"]["status"] == "draft"
    assert {warning["kind"] for warning in manifest["bundle_warnings"]} >= {"missing_artifact"}
    assert {"flight_path_plot", "robustness_summary"} <= {
        item["id"] for item in manifest["missing_evidence"] if item["kind"] == "artifact"
    }
    bundle_readme_text = bundle_readme.read_text(encoding="utf-8")
    assert "Start with `operator_dashboard.md`" in bundle_readme_text
    assert "operator_review_ui.html" in bundle_readme_text
    assert "local read-only browser view" in bundle_readme_text
    ui_text = operator_review_ui.read_text(encoding="utf-8")
    assert "ORBITAL Operator Review UI" in ui_text
    assert "Mission Verdict:" in ui_text
    assert "REVIEW REQUIRED" in ui_text
    assert "Modeled mission status" in ui_text
    assert "Top limiting constraint" in ui_text
    assert "Regulatory readiness" in ui_text
    assert "Evidence completeness" in ui_text
    assert "Regulatory documentation" in ui_text
    assert "Weather fallback" in ui_text
    assert "Robustness / uncertainty" in ui_text
    assert "Missing evidence" in ui_text
    assert "Evidence warnings" in ui_text
    assert "local review surface" in ui_text
    assert "decision support, not approval" in ui_text
    assert "does not approve a mission" in ui_text
    dashboard_text = operator_dashboard.read_text(encoding="utf-8")
    assert "ORBITAL Operator Evidence Dashboard" in dashboard_text
    assert "Mission Verdict: REVIEW REQUIRED" in dashboard_text
    assert "Mission Card" in dashboard_text
    assert "| Verdict | REVIEW REQUIRED |" in dashboard_text
    assert "10-Second Mission Read" in dashboard_text
    assert "Recommended Opening Sequence" in dashboard_text
    assert "| Signal | Current value | Operator cue |" in dashboard_text
    assert "Mission status: GO" in dashboard_text
    assert "Mission risk:" in dashboard_text
    assert "Top limiting constraint:" in dashboard_text
    assert "Regulatory readiness: OPERATOR_ACTION_REQUIRED" in dashboard_text
    assert "not approval, not authorization, not legal advice" in dashboard_text
    assert "[what_if_plan.md](what_if_plan.md)" in dashboard_text
    assert "[manifest.json](manifest.json)" in dashboard_text
    assert "[checksum_manifest.json](checksum_manifest.json)" in dashboard_text
    assert "flight_path.png" in dashboard_text
    assert "[autopilot_mission.csv](autopilot_mission.csv)" in dashboard_text
    assert "[mission_review.kml](mission_review.kml)" in dashboard_text
    bundle_summary_text = bundle_summary.read_text(encoding="utf-8")
    assert "Completeness score:" in bundle_summary_text
    assert "Reviewer Snapshot" in bundle_summary_text
    assert "Recommended Review Flow" in bundle_summary_text
    artifact_index_text = artifact_index.read_text(encoding="utf-8")
    assert "Evidence Bundle Artifact Index" in artifact_index_text
    assert "Open First" in artifact_index_text
    assert "Review Path" in artifact_index_text
    assert "Artifact Status Summary" in artifact_index_text
    assert "Recommended Opening Order" in artifact_index_text
    assert "Primary constraint-audit report" in artifact_index_text
    assert "What-if planning report" in artifact_index_text
    assert "Regulatory readiness report" in artifact_index_text
    assert "Lightweight operator review web UI" in artifact_index_text
    assert "Operator evidence dashboard" in artifact_index_text
    assert "Evidence bundle summary" in artifact_index_text
    checksums = json.loads(checksum_manifest.read_text(encoding="utf-8"))
    assert checksums["algorithm"] == "sha256"
    assert {item["bundle_path"] for item in checksums["files"]} >= {
        "manifest.json",
        "operator_review_ui.html",
        "operator_dashboard.md",
        "evidence_bundle_summary.md",
        "artifact_index.md",
    }

    summary_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "bundle-summary",
            str(bundle_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert summary_result.returncode == 0, summary_result.stdout + summary_result.stderr
    assert "ORBITAL Evidence Bundle Summary" in summary_result.stdout
    assert "Open first artifact:" in summary_result.stdout
    assert "operator_dashboard.md" in summary_result.stdout
    assert "Mission verdict: REVIEW REQUIRED" in summary_result.stdout
    assert "Modeled mission status: GO" in summary_result.stdout
    assert "Top limiting constraint:" in summary_result.stdout
    assert "Next operator action:" in summary_result.stdout

    open_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "open-first",
            str(bundle_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert open_result.returncode == 0, open_result.stdout + open_result.stderr
    assert "ORBITAL First Artifact To Open" in open_result.stdout
    assert "Open first artifact:" in open_result.stdout
    assert "operator_dashboard.md" in open_result.stdout

    verdict_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "verdict",
            str(bundle_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert verdict_result.returncode == 0, verdict_result.stdout + verdict_result.stderr
    assert "ORBITAL Mission Verdict" in verdict_result.stdout
    assert "Mission verdict: REVIEW REQUIRED" in verdict_result.stdout
    assert "Modeled mission status: GO" in verdict_result.stdout
    assert "Regulatory readiness: OPERATOR_ACTION_REQUIRED" in verdict_result.stdout
    assert "Next operator action:" in verdict_result.stdout

    verify_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "bundle-verify",
            str(bundle_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert verify_result.returncode == 0, verify_result.stdout + verify_result.stderr
    assert "Checksum OK: yes" in verify_result.stdout
    assert "Scenario metadata OK: yes" in verify_result.stdout

    top_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "top",
            str(bundle_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert top_result.returncode == 0, top_result.stdout + top_result.stderr
    assert "ORBITAL Top Limiting Constraint" in top_result.stdout
    assert "Top limiting constraint:" in top_result.stdout
    assert ": PASS, margin" in top_result.stdout
    assert "Recommended operator action:" in top_result.stdout
    assert "Selection detail:" in top_result.stdout

    review_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "bundle-review-validate",
            str(bundle_dir / "manifest.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert review_result.returncode == 0, review_result.stdout + review_result.stderr
    assert "Review metadata: VALID" in review_result.stdout
    assert "Operator review status: draft" in review_result.stdout

    serve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "serve-ui",
            str(bundle_dir),
            "--port",
            "8765",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert serve_result.returncode == 0, serve_result.stdout + serve_result.stderr
    assert "ORBITAL Operator Review UI" in serve_result.stdout
    assert "First page to open: operator_review_ui.html" in serve_result.stdout
    assert "Local review URL: http://127.0.0.1:8765/operator_review_ui.html" in (
        serve_result.stdout
    )
    assert "First evidence artifact:" in serve_result.stdout
    assert "operator_dashboard.md" in serve_result.stdout
    assert "Primary manifest data: manifest.json" in serve_result.stdout
    assert "Manifest status: available" in serve_result.stdout
    assert "Serving static evidence bundle files only." in serve_result.stdout
    assert "No backend database, accounts, auth, editing workflow, or file copying required." in (
        serve_result.stdout
    )
    assert "Dry run: server not started." in serve_result.stdout


def test_cli_overrides_yaml_settings_and_accepts_single_dash_aliases(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import mission_framework.cli as cli

    captured: dict[str, Any] = {}
    fake_problem = SimpleNamespace(robustness_cases=0)

    def fake_load_yaml(path: Path) -> dict[str, Any]:
        return {
            "scenario": {"name": "Fake Aircraft", "type": "aircraft"},
            "planner": {
                "iterations": 200,
                "restarts": 1,
                "seed": 42,
                "penalty_weight": 2000.0,
            },
            "robustness": {"cases": 20},
            "output": {"save_history": False},
        }

    def fake_build_problem(cfg: dict[str, Any]) -> SimpleNamespace:
        captured["build_cfg"] = copy.deepcopy(cfg)
        return fake_problem

    class FakeConstraints:
        hard_pass = True

        def worst(self, severity: Any) -> None:
            return None

        def to_jsonable(self) -> dict[str, bool]:
            return {"hard_pass": True}

    class FakeScoreReport:
        def to_jsonable(self) -> dict[str, float]:
            return {"total_score": 1.0}

    class FakePlanner:
        def __init__(self, cfg: Any):
            captured["planner_cfg"] = cfg

        def solve(self, problem: Any) -> Any:
            captured["problem"] = problem
            return SimpleNamespace(
                score=1.0,
                constraints=FakeConstraints(),
                score_report=FakeScoreReport(),
                robustness={"cases": problem.robustness_cases},
                plan=SimpleNamespace(kind="fake", metadata={}, waypoints=[]),
                sim_result=SimpleNamespace(),
                history=None,
            )

    written_paths: list[Path] = []

    def fake_write_json(out_path: Path, obj: Any) -> None:
        written_paths.append(out_path)

    monkeypatch.setattr(cli, "_load_yaml", fake_load_yaml)
    monkeypatch.setattr(cli, "validate_scenario_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "_build_problem", fake_build_problem)
    monkeypatch.setattr(cli, "Planner", FakePlanner)
    monkeypatch.setattr(cli, "_write_json", fake_write_json)
    monkeypatch.setattr(cli, "format_feasibility_report", lambda *args, **kwargs: "ok")

    outdir = tmp_path / "custom_runs"
    exit_code = cli.main(
        [
            str(ROOT / "examples" / "aircraft_uav_demo.yaml"),
            "-iterations",
            "7",
            "-restarts",
            "3",
            "-robustness",
            "4",
            "-seed",
            "99",
            "-outdir",
            str(outdir),
            "-no-plots",
        ]
    )

    assert exit_code == 0
    build_cfg = captured["build_cfg"]
    planner_cfg = captured["planner_cfg"]
    assert build_cfg["planner"]["iterations"] == 7
    assert build_cfg["planner"]["restarts"] == 3
    assert build_cfg["planner"]["seed"] == 99
    assert build_cfg["robustness"]["cases"] == 4
    assert planner_cfg.iterations == 7
    assert planner_cfg.restarts == 3
    assert planner_cfg.seed == 99
    assert captured["problem"].robustness_cases == 4

    scenario_dir = outdir.resolve() / "aircraft_uav_demo"
    assert written_paths
    assert all(path.parent == scenario_dir for path in written_paths)


def test_cli_validate_accepts_valid_aircraft_scenario() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "validate",
            "examples/aircraft_uav_demo.yaml",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALID:" in result.stdout
    assert "Scenario: UAV Multi-Waypoint Mission Demo" in result.stdout
    assert "Type: aircraft" in result.stdout
    assert result.stderr == ""


def test_cli_batch_writes_summary(monkeypatch, tmp_path: Path) -> None:
    import mission_framework.cli as cli

    scenario_path = tmp_path / "inspection.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "scenario": {"name": "Batch Inspection", "type": "aircraft"},
                "output": {"run_dir_name": "batch_inspection"},
            }
        ),
        encoding="utf-8",
    )
    batch_out = tmp_path / "batch"

    def fake_run_single(run_args: list[str]) -> int:
        outdir = Path(run_args[run_args.index("--outdir") + 1])
        run_dir = outdir / "batch_inspection"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "operator_evidence_bundle").mkdir()
        (run_dir / "inspection_constraint_audit.json").write_text(
            json.dumps(
                {
                    "status": "go",
                    "mission_risk": "low",
                    "top_limiting_constraint": {
                        "label": "Battery reserve margin",
                        "status": "pass",
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(cli, "_run_single_scenario", fake_run_single)

    exit_code = cli.main(["batch", str(scenario_path), "--outdir", str(batch_out), "--no-plots"])

    assert exit_code == 0
    csv_text = (batch_out / "batch_summary.csv").read_text(encoding="utf-8")
    md_text = (batch_out / "batch_summary.md").read_text(encoding="utf-8")
    assert "Batch Inspection" in csv_text
    assert "low" in csv_text
    assert "Battery reserve margin" in md_text
    assert "operator_evidence_bundle" in md_text


def test_cli_validate_reports_all_errors_for_invalid_scenario(tmp_path: Path) -> None:
    source = ROOT / "examples" / "cubesat_leo_demo.yaml"
    cfg = yaml.safe_load(source.read_text(encoding="utf-8"))
    invalid = copy.deepcopy(cfg)
    invalid["scenario"]["type"] = "spacecraft"
    invalid["orbit"]["time_step_s"] = 0
    invalid["mission"]["targets"][0]["lat_deg"] = 120.0
    invalid["spacecraft"]["initial_battery_Wh"] = 999.0

    scenario_path = tmp_path / "invalid_spacecraft.yaml"
    scenario_path.write_text(yaml.safe_dump(invalid), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mission_framework.cli",
            "validate",
            str(scenario_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "INVALID:" in result.stderr
    assert "Scenario validation failed" in result.stderr
    assert "orbit.time_step_s" in result.stderr
    assert "mission.targets[0].lat_deg" in result.stderr
    assert "spacecraft.initial_battery_Wh" in result.stderr
