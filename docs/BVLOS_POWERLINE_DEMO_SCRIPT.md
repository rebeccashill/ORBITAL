# BVLOS Powerline Inspection Demo Script

This walkthrough shows ORBITAL as a constraint-aware BVLOS inspection
feasibility and audit evidence workflow. The demo is designed around one
operator question:

> Can we safely and defensibly fly this mission?

Use this script for a customer, investor, or HBS-style product demo. It keeps
the narrative grounded in generated artifacts rather than treating ORBITAL as a
generic map or route-planning tool.

v1.0.13 emphasizes credibility and operator trust: the first screen explains
why the verdict needs review, what evidence is stale or operator-confirmed, and
which raw artifact should be opened first.

## Demo Setup

Regenerate the full demo artifacts, including plots:

```bash
python -m mission_framework.cli examples/bvlos_powerline_inspection_demo.yaml --outdir outputs
```

For a text-only refresh without PNG plots:

```bash
python -m mission_framework.cli examples/bvlos_powerline_inspection_demo.yaml --outdir outputs --no-plots
```

Launch the lightweight local review UI:

```bash
python -m mission_framework.cli serve-ui
```

Open the printed `operator_review_ui.html` URL first. The command serves the
generated BVLOS evidence bundle directly from
`outputs/bvlos_powerline_inspection/operator_evidence_bundle` with Python's
built-in static file server; there is no database, account setup, auth flow,
build step, or file-copying step.

Primary review surface:

- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_review_ui.html`

Primary source artifacts to open from the UI or filesystem:

- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_dashboard.md`
- `outputs/bvlos_powerline_inspection/inspection_constraint_audit.md`
- `outputs/bvlos_powerline_inspection/what_if_plan.md`
- `outputs/bvlos_powerline_inspection/regulatory_readiness_report.md`
- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/evidence_bundle_summary.md`
- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/artifact_index.md`
- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/manifest.json`
- `outputs/bvlos_powerline_inspection/operator_evidence_bundle/checksum_manifest.json`

## v1.0.13 Flow

Use this review order in the UI and narration:

```text
Verdict -> top constraint -> trust signals -> artifacts -> checksum
```

The first screen should answer five questions before the presenter opens a raw
file:

1. What is the mission verdict and next operator action?
2. What is the top modeled constraint?
3. Which trust signals require operator verification?
4. Which artifact should the reviewer open first?
5. Has checksum evidence been generated and verified?

Live weather hooks and regulatory provenance fields are documentation-only
readiness records unless verified outside ORBITAL. ORBITAL does not grant
approval, authorization, LAANC, legal advice, or operational clearance.

## Demo Arc

1. Start with the local operator review UI, not the map.
2. Use the first screen for the 30-second read: verdict, top constraint, trust
   signals, source artifacts, checksum readiness, freshness, and warnings.
3. Open the Markdown dashboard and audit artifacts to show that the evidence
   bundle remains the source of truth and the UI is read-only.
4. Drill into the constraint audit for baseline feasibility and top limiting
   constraint.
5. Show what-if alternatives and before/after improvements.
6. Show regulatory readiness as operator-confirmed, documentation-only
   decision support.
7. Finish with the raw Markdown, JSON, CSV, KML, PNG, manifest, dashboard, and
   checksum artifacts.

## 0. Operator Review UI

Launch and open:

```bash
python -m mission_framework.cli serve-ui
```

Presenter script:

> The first screen is a local, read-only review surface for the generated
> evidence bundle. It pulls the mission verdict, top modeled constraint,
> why-this-verdict explanation, model assumptions, weather and regulatory
> provenance, artifact freshness, raw evidence links, and checksum readiness
> into one scannable view. It is a demo and discovery aid, not a SaaS workflow
> and not an approval system.

Sample output:

```text
Mission Verdict: REVIEW REQUIRED
Modeled mission status: GO
Mission risk: LOW
Top limiting constraint: Wind / weather margin, PASS, margin 3.1 m/s
Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum
Regulatory readiness: OPERATOR_ACTION_REQUIRED
Evidence completeness: 100.0 %
Weather evidence: STALE sample/fallback evidence; operator should verify
Regulatory provenance: STALE, pending operator confirmation
Checksum evidence: VERIFY REQUIRED
Next operator action: Complete review items outside ORBITAL.
```

Emphasize the UI boundary language: it is read-only, it does not approve a
mission, and it does not replace approval, authorization, legal advice, LAANC,
or operational clearance. Then use the Source Artifacts links to open the
Markdown dashboard and supporting files. The Markdown, JSON, CSV, KML, PNG,
manifest, checksum, and dashboard artifacts remain accessible outside the UI.
Unavailable artifacts must render as unavailable text, not broken links.

## 1. Baseline Mission Feasibility

Open:

```text
outputs/bvlos_powerline_inspection/inspection_constraint_audit.md
```

Presenter script:

> ORBITAL starts with the operator's real question: can this BVLOS inspection be
> flown safely and defensibly under the modeled constraints? For this demo, the
> baseline powerline corridor mission is a GO with LOW modeled mission risk.

Sample output:

```text
Mission: BVLOS Powerline Inspection Demo
Status: GO
Mission risk: LOW
```

Then point to the constraint group table. The important move is that ORBITAL
does not merely draw the corridor route. It translates modeled constraints into
operator-readable status, margins, operational impact, and recommended action.

Baseline constraint summary:

| Constraint group | Status | Margin |
| --- | --- | ---: |
| Energy / battery reserve | PASS | 132.1 Wh |
| Weather / wind margin | PASS | 3.1 m/s |
| Geofence / no-fly-zone clearance | PASS | 276.7 m |
| Route completion | PASS | 1.0 completion |
| Turn / bank feasibility | PASS | 0.139 rad/s |

## 2. Top Limiting Constraint

Stay in:

```text
outputs/bvlos_powerline_inspection/inspection_constraint_audit.md
```

Presenter script:

> The route is feasible, but ORBITAL still identifies the constraint most worth
> watching. In this run, the top limiting constraint is the weather margin. It
> passes, but it carries the highest risk contribution because wind can quickly
> reduce endurance, tracking quality, and recovery margin.

Sample output:

```text
Top limiting constraint: Wind / weather margin, PASS with margin 3.1 m/s
```

Use the top three risk drivers section to explain that "GO" does not mean "stop
thinking." It means the current modeled plan passes, while the operator can see
which assumptions deserve the most review before dispatch.

Then open the Model Transparency section in the same audit. It records battery,
wind, geofence, route completion, turn feasibility, and robustness assumptions;
lists margin units and sources; explains why the top limiting constraint was
selected; and captures the scenario path, seed, iterations, robustness cases,
and command used to reproduce the report. Use the limitations notes to keep the
demo legally and technically honest about offline/sample weather and simplified
flight dynamics.

CLI shortcut:

```bash
python -m mission_framework.cli bundle-top outputs/bvlos_powerline_inspection/operator_evidence_bundle
```

This prints the top limiting constraint and recommended operator action without
rerunning optimization.

## 3. What-If Comparison

Open:

```text
outputs/bvlos_powerline_inspection/what_if_plan.md
```

Presenter script:

> ORBITAL then compares realistic planning alternatives. Instead of manually
> duplicating routes and guessing which adjustment helps, the operator can see
> how changes affect feasibility, time, energy, and the top limiter.

Baseline:

```text
Risk: LOW
Feasible: yes
Time: 140.0 s
Energy: 17.9 Wh
Battery margin: 132.1 Wh
Wind margin: 3.1 m/s
```

Useful scenario callouts:

| Scenario | Risk | Feasible | Operator meaning |
| --- | --- | --- | --- |
| Fewer waypoints | LOW | yes | Shorter sortie, better battery reserve |
| Lower speed | LOW | yes | Longer time, better energy and turn margin |
| Larger battery reserve requirement | MEDIUM | yes | Feasible, but reserve policy becomes the tighter review item |
| Relaunch / battery swap | LOW | yes | Stronger battery reserve by splitting the operation |

Before/after examples:

```text
Fewer waypoints improves battery reserve from 132.1 Wh to 138.2 Wh.
Lower speed improves turn / bank margin from 0.139 rad/s to 0.254 rad/s.
Relaunch / battery swap improves battery reserve from 132.1 Wh to 141.6 Wh.
```

## 4. Regulatory Readiness

Open:

```text
outputs/bvlos_powerline_inspection/regulatory_readiness_report.md
```

Presenter script:

> ORBITAL is legally honest here: this is decision support, not approval. It
> records what the operator must confirm outside ORBITAL, including LAANC,
> waiver or authorization coverage, visual observer support, airspace class,
> ground-risk notes, authority source, date checked, expiration, and operator
> confirmation status.

Sample output:

```text
Readiness state: OPERATOR_ACTION_REQUIRED
LAANC required: yes
Waiver / authorization required: yes
Airspace class: Class D
Visual observer required: yes
Regulatory evidence source: Operator-provided example authority source
Date checked: 2026-09-11T15:45:00Z
Expiration: 2026-12-31
Operator confirmation: pending_operator_confirmation
```

The key product boundary:

```text
ORBITAL provides decision support only and is not legal approval.
```

Then show the operator approval checklist. It includes LAANC confirmation,
waiver / authorization confirmation, visual observer assignment, crew briefing,
emergency / contingency planning, NOTAM / local restriction review, weather
minimums, and battery reserve confirmation.

## 5. Final Evidence Bundle

Open:

```text
outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_dashboard.md
outputs/bvlos_powerline_inspection/operator_evidence_bundle/evidence_bundle_summary.md
outputs/bvlos_powerline_inspection/operator_evidence_bundle/manifest.json
outputs/bvlos_powerline_inspection/operator_evidence_bundle/checksum_manifest.json
```

CLI shortcuts:

```bash
python -m mission_framework.cli serve-ui
python -m mission_framework.cli open-first outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli verdict outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli top outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-summary outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-verify outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-review-validate outputs/bvlos_powerline_inspection/operator_evidence_bundle
```

Presenter script:

> The end product is an evidence package an operator can review, store, and hand
> to stakeholders. It is not just a plan. It is a bundle with the constraint
> audit, regulatory readiness report, route artifacts, weather snapshot,
> downstream planning exports, manifest, index, and checksums. The browser UI
> helps reviewers discover and scan those artifacts, but it does not edit them
> or replace them as the record.

Sample output:

```text
Completeness score: 100.0 %
Artifacts present: 17 / 17
Missing artifact count: 0
Operator review status: ready for review
Manifest version: 1
UI schema: 1
Checksum evidence: VERIFY REQUIRED until verification is rerun on final files
```

Then open:

```text
outputs/bvlos_powerline_inspection/operator_evidence_bundle/artifact_index.md
```

Use the index to show that the bundle links the scenario YAML, plan JSON,
constraint audit, regulatory report, score breakdown, flight path plot,
robustness summary, operator memo, weather snapshot, autopilot CSV, KML review
file, manifest, summary, README, and checksum manifest.

## What Improved Since v1.0.12

- The first screen now has a dedicated "Why this verdict?" explanation and a
  review order strip for verdict, top constraint, trust signals, artifacts, and
  checksum.
- Manifest compatibility, UI schema expectations, optional-field fallback text,
  checksum readiness, and artifact freshness are visible near the first screen.
- Weather evidence is labeled as live, fallback, sample, stale, or missing, with
  source, timestamp, freshness, and operator action.
- Regulatory evidence provenance carries source, date checked, expiration,
  authority, and operator confirmation status as documentation-only records.
- Raw Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts
  are easy to open outside the UI; unavailable artifacts do not render as broken
  links.
- Demo language is more explicit that ORBITAL supports defensible review but
  does not grant approval, authorization, LAANC, legal advice, or clearance.

## Customer-Discovery Script: Credibility And Operator Trust

Use these prompts after the 30-second review path, while the UI and raw evidence
bundle are still visible:

1. "When your team reviews a BVLOS inspection today, what has to be visible in
   the first 30 seconds before you trust the package enough to keep reviewing?"
2. "Which stale or missing evidence would stop this mission from moving forward:
   weather, authorization, route exports, checksums, or something else?"
3. "Who is allowed to confirm regulatory evidence in your workflow, and where
   would that confirmation need to be recorded?"
4. "Does the why-this-verdict panel explain the decision well enough for a pilot,
   program manager, or customer stakeholder?"
5. "Which raw artifacts would you need to archive outside the UI for audit,
   handoff, or customer review?"
6. "What language would make it clearer that ORBITAL is decision support and
   evidence packaging, not approval or clearance?"

Close this section by saying:

> The product bet is trust. ORBITAL should make the operator faster without
> hiding the evidence, inventing approval, or pretending sample inputs are live
> operational facts.

## Screenshots And Sample Outputs

Use the screenshot set for polished README, demo, and Foundry-style visuals:

```text
docs/BVLOS_DEMO_SCREENSHOT_SET.md
```

The operator review UI should be the first captured artifact because it shows
the mission verdict, modeled mission status, mission risk, review order, top
limiting constraint, why-this-verdict derivation, manifest compatibility,
freshness, regulatory readiness, bundle completeness, weather evidence,
robustness, warnings, raw evidence links, and checksum readiness on one page.
Then capture the Markdown operator dashboard, constraint audit, what-if report,
regulatory report, artifact index, and the generated visuals below. Include
focused UI screenshots for the dashboard, Source Artifacts navigation, and Trust
/ Defensibility section. The UI is read-only; the Markdown evidence bundle
remains the source of truth.

The generated mission overview is the strongest visual lead for README or demo
docs:

![BVLOS mission overview](../outputs/bvlos_powerline_inspection/mission_overview.png)

The generated flight path plot remains useful when you need a simple route
visual:

![BVLOS powerline flight path](../outputs/bvlos_powerline_inspection/flight_path.png)

For a compact README snippet, use:

```text
30-second review path
Mission verdict: REVIEW REQUIRED
Modeled mission status: GO
Mission risk: LOW
Top limiting constraint: Wind / weather margin, PASS with margin 3.1 m/s
Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum
Open first page: operator_review_ui.html
Open first source artifact: operator_dashboard.md
Evidence bundle completeness: 100.0 %
Weather evidence: STALE sample/fallback evidence; operator should verify
Checksum evidence: VERIFY REQUIRED
Regulatory readiness: OPERATOR_ACTION_REQUIRED, operator-confirmed documentation-only
```

For a demo close, use:

> ORBITAL does not replace a pilot, a LAANC provider, an autopilot, or a legal
> approval workflow. It answers the preflight feasibility question and packages
> the evidence an operator needs to review before committing a crew. Live
> weather and regulatory fields remain operator-confirmed unless verified
> outside ORBITAL.
