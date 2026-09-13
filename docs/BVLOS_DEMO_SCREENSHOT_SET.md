# BVLOS Demo Screenshot Set

Captured images live in `docs/assets/bvlos_screenshots/`. Use this page for
README updates, demo walkthroughs, and Foundry-style materials. The set leads
with the operator review flow, then closes with the route plot.

## Screenshot Gallery

### Operator Dashboard

![Operator dashboard](assets/bvlos_screenshots/operator_dashboard.png)

Caption: The dashboard proves ORBITAL starts with the operator's 10-second
read: mission verdict, mission risk, top limiting constraint, regulatory
readiness, evidence completeness, and next action on one page.

### Constraint Audit

![Constraint audit](assets/bvlos_screenshots/constraint_audit.png)

Caption: The audit proves the constraint workflow is an operator review
artifact, not an engineering log. It shows the top limiter, plain-English
constraint language, status legend, and recommended operator action.

### What-If Comparison

![What-if comparison](assets/bvlos_screenshots/what_if_comparison.png)

Caption: The what-if report proves ORBITAL can compare baseline feasibility
against mission changes and show what changed without hiding the tradeoffs.

### Regulatory Readiness Report

![Regulatory readiness report](assets/bvlos_screenshots/regulatory_readiness.png)

Caption: The regulatory report proves the workflow is documentation-only and
legally honest. It summarizes LAANC, waiver or authorization, airspace, visual
observer, ground-risk, and unresolved regulatory items without implying
approval.

### Artifact Index

![Artifact index](assets/bvlos_screenshots/artifact_index.png)

Caption: The artifact index proves the evidence bundle has a clear opening
order and links operators to the dashboard, audit, what-if plan, regulatory
report, manifest, checksum manifest, plots, CSV, and KML files.

### Flight Path Plot

![Flight path plot](assets/bvlos_screenshots/flight_path_plot.png)

Caption: The flight path plot proves the bundle still includes a concrete route
visual showing the start point, waypoint sequence, and modeled flight path.

## Source Map

| Capture | Source artifact | Committed image |
| --- | --- | --- |
| Operator dashboard | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_dashboard.md` | `docs/assets/bvlos_screenshots/operator_dashboard.png` |
| Constraint audit | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/inspection_constraint_audit.md` | `docs/assets/bvlos_screenshots/constraint_audit.png` |
| What-if comparison | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/what_if_plan.md` | `docs/assets/bvlos_screenshots/what_if_comparison.png` |
| Regulatory readiness | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/regulatory_readiness_report.md` | `docs/assets/bvlos_screenshots/regulatory_readiness.png` |
| Artifact index | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/artifact_index.md` | `docs/assets/bvlos_screenshots/artifact_index.png` |
| Flight path plot | `outputs/bvlos_powerline_inspection/flight_path.png` | `docs/assets/bvlos_screenshots/flight_path_plot.png` |

## Compact Demo Flow

1. Open `operator_dashboard.md` for the 10-second mission read.
2. Open `inspection_constraint_audit.md` for the top limiting constraint and
   operator action.
3. Open `what_if_plan.md` to show how alternatives improve or preserve
   feasibility.
4. Open `regulatory_readiness_report.md` to reinforce decision-support-only
   regulatory language.
5. Open `artifact_index.md`, `manifest.json`, and `checksum_manifest.json` to
   show bundle completeness and auditability.
