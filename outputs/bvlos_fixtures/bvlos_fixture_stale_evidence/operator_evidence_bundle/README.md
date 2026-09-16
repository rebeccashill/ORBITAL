# ORBITAL Operator Evidence Bundle

This folder collects the artifacts an operator can review before a BVLOS inspection mission.

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, waiver system, legal approval system, or operational clearance system.

Regulatory metadata, authorization references, approval checklist items, and evidence fields in this bundle are documentation-only. They support operator review; they are not proof of authorization, legal approval, LAANC, waiver, or operational clearance.

Start with `operator_dashboard.md`, then use `artifact_index.md` to open individual artifacts. `evidence_bundle_summary.md` summarizes completeness, and `checksum_manifest.json` provides lightweight SHA-256 checksums for files in this bundle. For a local read-only browser view, open `operator_review_ui.html`; the Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts remain accessible outside the UI.

## Open This First

`operator_dashboard.md` is the first file to open. It gives the mission verdict, mission risk, top limiting constraint, regulatory readiness, evidence completeness, and next operator action before the reviewer drills into details.
Open `operator_review_ui.html` for the same operator review signals in a lightweight local web UI. Opening or reviewing that page does not approve, authorize, clear, or legally validate a mission.

## How To Review This Bundle

Start with the dashboard, then open the constraint audit for feasibility and top-limiter rationale, the what-if report for mission tradeoffs, and the regulatory readiness report for documentation-only action items. Use the evidence summary to check missing evidence, warnings, reviewer metadata, and operator decision status.

## How To Archive This Bundle

Archive the full `operator_evidence_bundle/` folder after review. Keep `manifest.json`, `checksum_manifest.json`, the scenario YAML, and all linked artifacts together so a later reviewer can verify the files came from the same scenario and generation run.

## Completeness And Verification

Artifact completeness reports whether expected bundle files are present. Regulatory documentation completeness is reported separately because optional regulatory evidence fields are documentation aids, not generated artifact failures or approvals. `checksum_manifest.json` records lightweight SHA-256 checksums; run `python -m mission_framework.cli bundle-verify <bundle>` to check whether archived files still match the bundle manifest.
Manifest version: 1. UI schema version: 1. Unavailable artifacts render as unavailable labels rather than links.

Recommended opening order:

1. `operator_dashboard.md` for the 10-second mission read.
2. `inspection_constraint_audit.md` for feasibility and top-limiter rationale.
3. `what_if_plan.md` for improvement options.
4. `regulatory_readiness_report.md` for documentation-only regulatory review.
5. `manifest.json` and `checksum_manifest.json` for archive checks.

## Bundle Summary

- Completeness score: 100.0 %
- Artifact completeness score: 100.0 %
- Regulatory documentation completeness score: 100.0 %
- Missing evidence items: 0
- Bundle warnings: 2
- Operator review status: ready for review
- Reviewer: Fixture reviewer
- Review timestamp UTC: 2026-09-15T05:24:50Z
- Operator decision: pending operator review
- Review notes: Fixture with stale weather and stale regulatory provenance for review-required evidence testing.

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

## Weather / Live Evidence Readiness

- Status: STALE
- Mode: sample
- Source: offline Open-Meteo-shaped sample
- Provider: open_meteo
- Timestamp: 2026-09-11T16:00:00Z
- Freshness: stale
- Operator action: Refresh weather evidence close to launch and keep the source timestamp with the evidence bundle. Operator should verify field conditions.
- Live provider hook: documentation-only; live weather integration can populate this field but is not required.

## Regulatory Evidence Provenance

- Status: STALE
- Source: Operator-provided example authority source for documentation-only demo
- Date checked: 2026-09-11T15:45:00Z
- Expiration: 2026-12-31
- Authority: FAA / LAANC provider placeholder
- Operator confirmation status: pending_operator_confirmation
- Operator action: Refresh regulatory evidence checks before relying on this bundle for review. Operator should verify regulatory inputs.
- Documentation-only: ORBITAL does not grant approval, authorization, LAANC, legal advice, or operational clearance.

## Flight-Planning Exports

Planning artifact only. ORBITAL does not provide LAANC, waivers, authorizations, legal approval, autopilot control, or operational clearance.
