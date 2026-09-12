# ORBITAL Operator Evidence Bundle

This folder collects the artifacts an operator can review before a BVLOS inspection mission.

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, waiver system, legal approval system, or operational clearance system.

Regulatory metadata, authorization references, approval checklist items, and evidence fields in this bundle are documentation-only. They support operator review; they are not proof of authorization, legal approval, LAANC, waiver, or operational clearance.

Start with `operator_dashboard.md`, then use `artifact_index.md` to open individual artifacts. `evidence_bundle_summary.md` summarizes completeness, and `checksum_manifest.json` provides lightweight SHA-256 checksums for files in this bundle.

## Bundle Summary

- Completeness score: 100.0 %
- Artifact completeness score: 100.0 %
- Regulatory documentation completeness score: 100.0 %
- Missing evidence items: 0
- Bundle warnings: 0
- Operator review status: ready for review
- Reviewer: not provided
- Review timestamp UTC: not provided
- Operator decision: pending operator review
- Review notes: Demo bundle ready for operator review; final approval remains outside ORBITAL.

## Contents

- Scenario YAML: `scenario.yaml` (included)
- Plan JSON: `plan.json` (included)
- Primary constraint-audit report: `inspection_constraint_audit.md` (included)
- Constraint audit JSON: `inspection_constraint_audit.json` (included)
- Regulatory readiness JSON: `regulatory_readiness_report.json` (included)
- Regulatory readiness report: `regulatory_readiness_report.md` (included)
- What-if planning report: `what_if_plan.md` (included)
- What-if planning JSON: `what_if_plan.json` (included)
- Score breakdown: `score.json` (included)
- Flight path plot: `flight_path.png` (included)
- Robustness summary: `robustness.json` (included)
- Plain-English go/no-go memo: `operator_memo.md` (included)
- Weather snapshot: `weather.json` (included)
- Autopilot mission CSV: `autopilot_mission.csv` (included)
- Mission review KML: `mission_review.kml` (included)
- Flight-planning exports manifest: `flight_planning_exports.json` (included)
- Flight-planning exports README: `flight_planning_exports.md` (included)

## Regulatory Readiness

- Readiness report JSON: included
- Readiness report Markdown: included
- Approval checklist source: regulatory_readiness_report.json
- Approval checklist items: 8
- Missing documentation-only evidence fields: none
- Documentation-only status: regulatory evidence and checklist items are operator review aids, not approvals.

## Approval Checklist

- [ ] Confirm LAANC / controlled-airspace authorization
- [ ] Confirm waiver / authorization coverage
- [ ] Confirm visual observer assignment
- [ ] Confirm crew briefing completed
- [ ] Confirm emergency / contingency plan
- [ ] Confirm NOTAM / local restriction review
- [ ] Confirm weather minimums
- [ ] Confirm battery reserve

## Weather Source

- Source: offline Open-Meteo-shaped sample
- Provider: open_meteo
- Timestamp: 2026-09-11T16:00:00Z
- Fallback used: yes

## Flight-Planning Exports

Planning artifact only. ORBITAL does not provide LAANC, waivers, authorizations, legal approval, autopilot control, or operational clearance.
