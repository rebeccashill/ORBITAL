# BVLOS Evidence Fixture Matrix

These fixtures exercise distinct operator-review evidence states before customer
discovery. First-time reviewers should start with the clean ready fixture:
`outputs/bvlos_fixtures/bvlos_fixture_ready_evidence/operator_evidence_bundle/operator_review_ui.html`.

| Fixture | Intended state | What it demonstrates |
| --- | --- | --- |
| `bvlos_ready_evidence_fixture.yaml` | Clean / ready bundle | GO mission, packaged fresh weather, documented regulatory provenance, complete artifacts, and no fixture warnings |
| `bvlos_stale_evidence_fixture.yaml` | Stale evidence | GO mission with stale weather and stale regulatory provenance warnings that should remain visible but non-blocking |
| `bvlos_missing_artifact_fixture.yaml` | Missing artifact | GO mission where the robustness artifact is unavailable and rendered as missing evidence without a broken link |
| `bvlos_modify_no_go_fixture.yaml` | Modify / no-go mission | Hard battery-reserve failure drives `constraint_audit.status == modify`; missing robustness still renders as unavailable evidence |

Generated fixture review bundles are committed under `outputs/bvlos_fixtures/`.
Each fixture keeps the full `operator_evidence_bundle/` so UI health can verify
every artifact link from a fresh checkout.

Saved UI health artifacts live under `docs/assets/bvlos_fixture_ui/`, with
desktop 1366px, desktop 1440px, desktop 1920px, tablet, mobile, print preview,
and PDF artifacts for every fixture state.

Regenerate fixture outputs with:

```bash
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_ready_evidence_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_stale_evidence_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_missing_artifact_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_modify_no_go_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
```

Run the fixture release gate with:

```bash
python -m mission_framework.cli ui-health
```
