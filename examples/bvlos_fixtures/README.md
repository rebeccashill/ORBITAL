# BVLOS Evidence Fixture Matrix

These fixtures exercise distinct operator-review evidence states before customer discovery.

| Fixture | Intended state | Primary assertion |
| --- | --- | --- |
| `bvlos_ready_evidence_fixture.yaml` | Clean / ready bundle | GO mission, packaged fresh weather, documented regulatory provenance, complete artifacts |
| `bvlos_stale_evidence_fixture.yaml` | Stale evidence | Stale weather and stale regulatory provenance warnings |
| `bvlos_missing_artifact_fixture.yaml` | Missing artifact | Robustness artifact is unavailable and rendered as missing evidence |
| `bvlos_modify_no_go_fixture.yaml` | Modify / no-go mission | Hard battery-reserve failure drives `constraint_audit.status == modify` |

Representative generated outputs are committed under `outputs/bvlos_fixtures/`.
Each fixture keeps `manifest.json`, `operator_dashboard.md`,
`operator_review_ui.html`, and `checksum_manifest.json` as review snapshots.
Regenerate them with:

```bash
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_ready_evidence_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_stale_evidence_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_missing_artifact_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
python -m mission_framework.cli examples/bvlos_fixtures/bvlos_modify_no_go_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs/bvlos_fixtures
```
