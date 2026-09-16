# Evidence Bundle Summary

Human-readable review summary for the operator evidence bundle.

Mission: bvlos_ready_evidence_fixture
Completeness score: 100.0 %
Artifacts present: 17 / 17
Missing artifact count: 0
Artifact completeness score: 100.0 %
Regulatory documentation completeness score: 100.0 %
Operator review status: ready for review
Reviewer: Fixture reviewer
Review timestamp UTC: 2026-09-15T05:24:50Z
Operator decision: pending operator review
Review notes: BVLOS Ready Evidence Fixture generated for ORBITAL fixture matrix validation.
Generated timestamp UTC: 2026-09-15T05:24:50Z
ORBITAL version: 1.0.17
Scenario SHA-256: 2f1fd0b0d63f9d2a4b36f1beea6614674aa0a4cfaa71fcc02a3b07f131c4fa38
Command used: python -m mission_framework.cli examples\bvlos_fixtures\bvlos_ready_evidence_fixture.yaml --generated-at 2026-09-15T05:24:50Z --outdir outputs\bvlos_fixtures
Manifest version: 1
UI schema version: 1

ORBITAL evidence bundles are decision-support packages. Bundle completeness, review status, review notes, operator decisions, and checksums do not provide legal approval, LAANC, waivers, authorizations, operational clearance, legal advice, or permission to fly.

## Reviewer Snapshot

| Signal | Value | Reviewer use |
| --- | --- | --- |
| Open first | [operator_dashboard.md](operator_dashboard.md) | Start here for the fastest mission read. |
| Bundle completeness | 100.0 % (17 / 17 artifacts present) | Confirms expected files are present. |
| Artifact completeness | 100.0 % (17 / 17 artifacts present) | Separates file presence from regulatory documentation quality. |
| Regulatory documentation completeness | 100.0 % (11 / 11 fields documented) | Shows optional evidence fields captured for review. |
| Missing evidence | 0 item(s) | Review before accepting or archiving the bundle. |
| Bundle warnings | 0 warning(s) | Resolve stale, missing, or mismatched artifacts. |
| Manifest compatibility | version 1, UI schema 1 | Confirms the UI-facing field contract for local review. |
| Weather evidence | PACKAGED | Confirm packaged weather evidence against launch-time field conditions. Operator should verify the source outside ORBITAL. |
| Regulatory provenance | DOCUMENTED | Keep source, date checked, expiration, and confirmation record with the bundle. Operator should verify regulatory inputs. |
| Checksum evidence | VERIFY REQUIRED | Run bundle checksum verification after generation and before archiving or sharing the evidence bundle. |
| Robustness | PASS: 1 case(s), hard pass rate 100.0 %, worst hard margin 0.166. Confidence from configured robustness cases is scenario-limited and should be reviewed against operator uncertainty assumptions. | Review uncertainty assumptions before release. |
| Evidence warnings | CLEAR: 0 missing artifact(s), 0 stale artifact(s), 0 missing evidence item(s), 0 bundle warning(s) | Check stale, missing, or mismatched evidence before archiving. |
| Review status | ready for review | Current operator review state. |
| Operator decision | pending operator review | Documentation-only review outcome. |

## Trust And Defensibility

- Sample data / demo scenario note: Scenario data note: verify route, weather, regulatory, crew, and customer evidence before operational use. Operator should verify source inputs.
- Weather evidence readiness: PACKAGED: packaged weather evidence from Operator-packaged field weather observation. Confirm it against launch-time field conditions. Timestamp: 2026-09-15T05:15:00Z.
- Regulatory evidence provenance: DOCUMENTED: regulatory evidence is documented for review. Source: Operator planning record; checked: 2026-09-15T04:30:00Z; expiration: 2026-12-31; authority: Operator internal review; confirmation: not_required.
- Checksum evidence readiness: Checksum manifest is generated with the bundle; verification must be run against the final archived files.
- Uncertainty / robustness status: PASS: 1 case(s), hard pass rate 100.0 %, worst hard margin 0.166. Confidence from configured robustness cases is scenario-limited and should be reviewed against operator uncertainty assumptions.
- Stale or missing evidence status: CLEAR: 0 missing artifact(s), 0 stale artifact(s), 0 missing evidence item(s), 0 bundle warning(s)

## Start Here

- Operator dashboard: [operator_dashboard.md](operator_dashboard.md)
- Primary constraint audit: [inspection_constraint_audit.md](inspection_constraint_audit.md)
- What-if plan: [what_if_plan.md](what_if_plan.md)
- Regulatory readiness report: [regulatory_readiness_report.md](regulatory_readiness_report.md)
- Artifact index: [artifact_index.md](artifact_index.md)
- Manifest JSON: [manifest.json](manifest.json)
- Checksum manifest: [checksum_manifest.json](checksum_manifest.json)

## Recommended Review Flow

1. Open the operator dashboard for the 10-second mission read.
2. Confirm the top limiting constraint in the primary constraint audit.
3. Review what-if changes if a margin is tight or a mission assumption changes.
4. Confirm regulatory readiness outside ORBITAL.
5. Verify the manifest and checksum manifest before archiving or sharing.

## UI Manifest Compatibility

| Contract | Value |
| --- | --- |
| Manifest version | 1 |
| UI schema version | 1 |
| Required top-level fields | 15 expected |
| Artifact entry fields | id, label, bundle_path, present |
| Optional fallback fields | 15 documented |
| Outside-UI artifact access | yes |
| Unavailable artifact policy | Unavailable artifacts render as non-link unavailable labels in the review UI and Markdown dashboard; they must not be emitted as hrefs. |

Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts remain accessible as files in this evidence bundle. The UI is a convenience surface, not the source of truth.

## Missing Evidence

- none

## Bundle Warnings

- none

## Regulatory Documentation

- Missing optional documentation fields: 0
- Documented optional fields: 11 / 11
- Approval checklist items: 5

## Review Summary

- Review status: ready for review
- Operator decision: pending operator review
- Reviewer: Fixture reviewer
- Review timestamp UTC: 2026-09-15T05:24:50Z
- Review notes: BVLOS Ready Evidence Fixture generated for ORBITAL fixture matrix validation.
