# BVLOS Demo Screenshot Set

Captured images live in `docs/assets/bvlos_screenshots/`. Use this page for
README updates, demo walkthroughs, and Foundry-style materials. The set leads
with the read-only operator review UI, then opens the Markdown evidence bundle
that remains the source of truth, and closes with the route plot.

## Screenshot Gallery

### Web UI Dashboard

![Operator review UI](assets/bvlos_screenshots/operator_review_ui.png)

Caption: The dashboard proves the local UI can give reviewers a 30-second read
of the generated BVLOS evidence bundle: mission verdict, modeled status, risk,
top constraint, next action, readiness, completeness, weather fallback,
robustness, and warning counts. It is read-only and does not approve,
authorize, or replace the underlying evidence bundle.

### UI Artifact Navigation

![UI artifact navigation](assets/bvlos_screenshots/operator_review_ui_artifact_navigation.png)

Caption: The navigation panel proves the UI is a discovery layer over the
source-of-truth bundle. It makes the recommended first artifact obvious and
links directly to the Markdown, JSON, image, CSV, KML, and checksum files
without hiding or mutating them.

### UI Trust / Defensibility

![UI trust and defensibility](assets/bvlos_screenshots/operator_review_ui_trust_defensibility.png)

Caption: The trust section proves the UI surfaces defensibility signals without
turning them into approval: weather fallback status, robustness status, model
context notes, and sample-data/demo caveats remain visible during review.

### Markdown Operator Dashboard

![Operator dashboard](assets/bvlos_screenshots/operator_dashboard.png)

Caption: The Markdown dashboard proves the source evidence remains accessible
outside the UI. It records the operator's mission read, mission verdict,
mission risk, top limiting constraint, regulatory readiness, evidence
completeness, and next action in the bundle of record.

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
| Web UI dashboard | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_review_ui.html` | `docs/assets/bvlos_screenshots/operator_review_ui.png` |
| UI artifact navigation | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_review_ui.html#source-artifacts` | `docs/assets/bvlos_screenshots/operator_review_ui_artifact_navigation.png` |
| UI trust / defensibility | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_review_ui.html#trust-defensibility` | `docs/assets/bvlos_screenshots/operator_review_ui_trust_defensibility.png` |
| Markdown operator dashboard | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_dashboard.md` | `docs/assets/bvlos_screenshots/operator_dashboard.png` |
| Constraint audit | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/inspection_constraint_audit.md` | `docs/assets/bvlos_screenshots/constraint_audit.png` |
| What-if comparison | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/what_if_plan.md` | `docs/assets/bvlos_screenshots/what_if_comparison.png` |
| Regulatory readiness | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/regulatory_readiness_report.md` | `docs/assets/bvlos_screenshots/regulatory_readiness.png` |
| Artifact index | `outputs/bvlos_powerline_inspection/operator_evidence_bundle/artifact_index.md` | `docs/assets/bvlos_screenshots/artifact_index.png` |
| Flight path plot | `outputs/bvlos_powerline_inspection/flight_path.png` | `docs/assets/bvlos_screenshots/flight_path_plot.png` |

## Compact Demo Flow

1. Run `python -m mission_framework.cli serve-ui` and open the printed
   `operator_review_ui.html` URL for the 30-second mission read.
2. State the boundary: the UI is local and read-only; the Markdown, JSON, CSV,
   KML, and checksum files remain the source of truth.
3. Open `operator_dashboard.md` from Source Artifacts to show the bundle of
   record.
4. Open `inspection_constraint_audit.md` for the top limiting constraint and
   operator action.
5. Open `what_if_plan.md` to show how alternatives improve or preserve
   feasibility.
6. Open `regulatory_readiness_report.md` to reinforce decision-support-only
   regulatory language.
7. Open `artifact_index.md`, `manifest.json`, and `checksum_manifest.json` to
   show bundle completeness and auditability.
