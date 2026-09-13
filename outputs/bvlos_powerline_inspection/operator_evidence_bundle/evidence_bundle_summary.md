# Evidence Bundle Summary

Human-readable review summary for the operator evidence bundle.

Mission: bvlos_powerline_inspection_demo
Completeness score: 100.0 %
Artifacts present: 17 / 17
Missing artifact count: 0
Artifact completeness score: 100.0 %
Regulatory documentation completeness score: 100.0 %
Operator review status: ready for review
Reviewer: not provided
Review timestamp UTC: not provided
Operator decision: pending operator review
Review notes: Demo bundle ready for operator review; final approval remains outside ORBITAL.
Generated timestamp UTC: 2026-09-13T03:23:21Z
ORBITAL version: 1.0.11
Scenario SHA-256: 25b9be4703966407b17a062cdc2547d86ed65bf9636c8b1edb7790c0fcdb9238
Command used: C:\Users\shill\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m mission_framework.cli examples/bvlos_powerline_inspection_demo.yaml --outdir outputs

ORBITAL evidence bundles are decision-support packages. Bundle completeness, review status, review notes, operator decisions, and checksums do not provide legal approval, LAANC, waivers, authorizations, operational clearance, legal advice, or permission to fly.

## Reviewer Snapshot

| Signal | Value | Reviewer use |
| --- | --- | --- |
| Open first | [operator_dashboard.md](operator_dashboard.md) | Start here for the fastest mission read. |
| Bundle completeness | 100.0 % (17 / 17 artifacts present) | Confirms expected files are present. |
| Artifact completeness | 100.0 % (17 / 17 artifacts present) | Separates file presence from regulatory documentation quality. |
| Regulatory documentation completeness | 100.0 % (8 / 8 fields documented) | Shows optional evidence fields captured for review. |
| Missing evidence | 0 item(s) | Review before accepting or archiving the bundle. |
| Bundle warnings | 0 warning(s) | Resolve stale, missing, or mismatched artifacts. |
| Weather fallback | FALLBACK USED | Refresh current field weather and keep the source with the bundle. |
| Robustness | PASS: 20 case(s), hard pass rate 100.0 %, worst hard margin 0.139 | Review uncertainty assumptions before release. |
| Evidence warnings | CLEAR: 0 missing artifact(s), 0 stale artifact(s), 0 missing evidence item(s), 0 bundle warning(s) | Check stale, missing, or mismatched evidence before archiving. |
| Review status | ready for review | Current operator review state. |
| Operator decision | pending operator review | Documentation-only review outcome. |

## Trust And Defensibility

- Sample data / demo scenario note: Sample data / demo scenario: this bundle uses demonstration planning inputs, including offline or sample weather where configured. Replace route, weather, regulatory, crew, and customer evidence before operational use.
- Weather fallback status: FALLBACK USED: source offline Open-Meteo-shaped sample, timestamp 2026-09-11T16:00:00Z, reason weather.use_live is false; using offline sample
- Uncertainty / robustness status: PASS: 20 case(s), hard pass rate 100.0 %, worst hard margin 0.139
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

## Missing Evidence

- none

## Bundle Warnings

- none

## Regulatory Documentation

- Missing optional documentation fields: 0
- Documented optional fields: 8 / 8
- Approval checklist items: 8

## Review Summary

- Review status: ready for review
- Operator decision: pending operator review
- Reviewer: not provided
- Review timestamp UTC: not provided
- Review notes: Demo bundle ready for operator review; final approval remains outside ORBITAL.
