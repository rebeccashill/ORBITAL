# ORBITAL

[![CI](https://github.com/rebeccashill/ORBITAL/actions/workflows/ci.yml/badge.svg)](https://github.com/rebeccashill/ORBITAL/actions/workflows/ci.yml)

**BVLOS Inspection Feasibility And Evidence**

Constraint audits, what-if planning, regulatory readiness, and evidence bundles
for drone inspection operators.

Current release: `v1.0.16`

> ORBITAL tells inspection teams whether a BVLOS mission is feasible before
> they send a crew.

ORBITAL is a preflight decision-support product for inspection operators who
need more than a route on a map. It turns route, vehicle, weather, geofence, and
regulatory metadata into a mission verdict, top limiting constraint, what-if
comparisons, and a review-ready evidence bundle before field time is committed.

Current product focus: make ORBITAL's BVLOS evidence workflow faster to scan,
clearer to demo, and more operator-friendly before customer-discovery and
Foundry-readiness work.

## What Improved In v1.0.16

v1.0.16 makes the BVLOS operator demo easier to run, scan, print, validate,
and explain before customer discovery.

- `run_all.py` now prints periodic "still running" progress while long demo
  commands execute, so optimization and robustness runs no longer look frozen
  while they are working.
- The desktop operator review UI packs review cards into deliberate stacks
  instead of row-stretching them. Weather / Live Evidence, Evidence
  Completeness, Trust / Defensibility, Warnings, and Artifact Navigation now
  sit closer together with consistent spacing.
- The Evidence Completeness card is shorter and clearer: it separates artifact
  coverage, artifacts present, missing evidence, and bundle warnings.
- The print/demo view uses compact artifact freshness columns and block-based
  review sections to reduce empty space in PDF or customer-discovery printouts.
- Demo generation accepts a fixed `--generated-at` timestamp so committed BVLOS
  evidence outputs can stay deterministic when refreshing the bundle.
- Operator review tests now parse the generated HTML structure, verify embedded
  manifest JSON against `manifest.json`, and ensure artifact links point only
  to available bundle files.
- The operator review UI health check now covers 1366px, 1440px, 1920px,
  tablet, mobile, print/PDF spacing, heading order, skip-link behavior,
  keyboard focus, and color contrast.
- `python -m mission_framework.cli ui-health` runs the pre-release layout and
  accessibility check against a generated evidence bundle.
- The generated BVLOS evidence bundle and checksum manifest are refreshed so
  `operator_review_ui.html` matches the current layout.

## Positioning

### Who This Is For

ORBITAL is for drone inspection teams planning BVLOS or BVLOS-adjacent missions
where the cost of a weak preflight decision is high: utilities, pipeline
operators, rail networks, renewable-energy owners, industrial sites, and
emergency infrastructure teams.

It is especially useful for UAS program managers, mission planners, remote
pilots in command, visual observer coordinators, and analysts who need a clear
mission review package before sending people and aircraft into the field.

### What Problem This Solves

Inspection teams need to know whether a planned mission is feasible,
defensible, and ready for operator review. Generic planning outputs often leave
that answer scattered across maps, weather notes, battery assumptions,
authorization records, and informal judgment calls.

ORBITAL pulls those pieces into one workflow: model the mission, audit the
constraints, identify the top limiter, compare practical alternatives, document
regulatory readiness, and package the evidence for review.

### Why Generic Drone Tools Are Not Enough

Route planners help draw paths. Fleet tools track assets. Autopilots execute
commands. LAANC providers handle airspace authorization. GIS viewers show
spatial context.

ORBITAL fills the gap before dispatch: it asks whether the mission can be
safely and defensibly flown under battery, wind, geofence, route-completion,
turn-feasibility, regulatory, and evidence constraints. The output is not just
a route; it is a constraint audit and operator evidence package.

### Why ORBITAL Now

Infrastructure operators are pushing drone programs toward longer, more
repeatable, and more accountable inspection workflows. As missions become more
complex, teams need preflight evidence that explains the decision, not only a
mission file that executes it.

ORBITAL is built for that moment: it turns feasibility, assumptions,
limitations, regulatory documentation, and review metadata into artifacts an
operator can inspect, archive, and defend.

### Decision Support, Not Approval

ORBITAL is not a drone autopilot, LAANC provider, live UTM service, legal
advisor, or regulatory approval system. It does not replace a licensed remote
pilot, operational safety review, waiver, authorization, or customer-specific
compliance process.

ORBITAL recommends and documents candidate plans. Human operators remain
responsible for approvals, release decisions, and flight execution.

### Current Capabilities

- Drone and aircraft multi-waypoint optimization
- Battery, wind, geofence, and route feasibility checks
- Primary constraint-audit reports with pass / warning / fail groups,
  operator-facing explanations, and recommended actions
- Spacecraft 7-day scheduling and operations planning as technical depth
- Simulation-based optimization with constraints
- Monte Carlo robustness analysis
- Structured reporting with JSON and CSV exports
- Automated visualization for flight paths, timelines, and performance plots

See [Differentiation](docs/DIFFERENTIATION.md) for the full positioning story,
comparison table, and product-category boundary. See
[Market Proof](docs/MARKET_PROOF.md) for the inspection-operator problem
statement, buyer and user assumptions, target customer profiles, and top
alternatives.

For a presenter-ready BVLOS walkthrough, see the
[BVLOS powerline demo script](docs/BVLOS_POWERLINE_DEMO_SCRIPT.md). The
v1.0.16 operator review starts with
`outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_review_ui.html`;
`operator_dashboard.md` remains the first source artifact to open from the raw
evidence bundle.
For a committed screenshot gallery, see the
[BVLOS demo screenshot set](docs/BVLOS_DEMO_SCREENSHOT_SET.md).
The constraint-audit report remains the primary feasibility artifact: it
translates modeled battery, weather, geofence, route-completion, and
turn-feasibility constraints into operator-readable status, impact, and
recommended action.

ORBITAL's current differentiators are:

- Constraint-first planning rather than map-first planning
- Transparent score and feasibility breakdowns
- Battery, wind, geofence, and route-completion evidence
- Monte Carlo robustness checks for uncertain mission conditions
- Exportable JSON/CSV artifacts for operator review and audit trails
- Regulatory readiness reports that document LAANC, waiver/authorization,
  airspace, visual observer, ground-risk, authorization evidence, assumptions,
  and unresolved items without implying legal approval
- Operator approval checklists that keep final confirmations with the pilot-in-
  command and operator
- Operational evidence readiness that distinguishes live, fallback, sample,
  stale, packaged, and missing weather evidence while keeping live and
  regulatory fields documentation-only until verified outside ORBITAL
- Verdict derivation panels that show how mission status, regulatory readiness,
  missing evidence, and warning counts produce the review verdict
- Evidence bundle manifests that surface regulatory metadata, approval
  checklist status, weather freshness, regulatory provenance, checksum
  readiness, and missing documentation-only evidence fields for operator review
  without treating them as approvals
- Evidence bundle summaries, artifact indexes, completeness scores, review
  status, and SHA-256 checksum manifests for operator audit packages

### Technical Depth

The spacecraft module remains part of the repository as a demonstration of the
same planning architecture applied to a harder scheduling domain. For the current
venture story, spacecraft planning should be treated as technical depth and
future expansion rather than the initial market wedge.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/rebeccashill/ORBITAL.git
cd ORBITAL
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 2. Run Both Domains

```bash
python run_all.py --fast --no-plots
```

For full plots and default robustness settings:

```bash
python run_all.py
```

Longer runs can spend a minute or two inside optimization or robustness checks.
`run_all.py` prints periodic progress lines and writes full command output to
`runs_logs/` so the terminal does not appear stuck while a demo is still
running.

Outputs are saved to:

```text
runs/aircraft_uav_demo/
runs/cubesat_leo_demo/
```

### 3. Validate Scenario YAML

```bash
orbital validate examples/aircraft_uav_demo.yaml
orbital validate examples/cubesat_leo_demo.yaml
```

Module form:

```bash
python -m mission_framework.cli validate examples/aircraft_uav_demo.yaml
```

See [Scenario Authoring Guide](docs/SCENARIO_AUTHORING.md) for YAML structure, units, examples, and common validation errors.

### 4. Optional Individual Demo Commands

Aircraft:

```bash
orbital examples/aircraft_uav_demo.yaml --iterations 200 --restarts 1 --robustness 20 --seed 0
```

Spacecraft:

```bash
orbital examples/cubesat_leo_demo.yaml --iterations 200 --restarts 1 --robustness 10 --seed 0
```

Use `--no-plots` when you only want JSON/CSV artifacts:

```bash
python run_all.py --fast --no-plots
```

The documented CLI flags use standard double dashes, such as `--seed` and
`--iterations`. The main run command also accepts single-dash compatibility
aliases such as `-seed`, `-iterations`, `-restarts`, `-robustness`, `-outdir`,
and `-no-plots`.

---

## Example Outputs

### BVLOS Powerline Demo Snapshot

The BVLOS demo leads with feasibility and evidence, not just a map:

```text
30-second review path
Mission verdict: REVIEW REQUIRED
Modeled mission status: GO
Mission risk: LOW
Top limiting constraint: Wind / weather margin, PASS with margin 3.1 m/s
Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum
Open first page: operator_review_ui.html
Open first source artifact: operator_dashboard.md
Weather evidence: STALE sample/fallback evidence; operator should verify
Checksum evidence: VERIFY REQUIRED before archive or sharing
Evidence bundle completeness: 100.0 %
Regulatory readiness: OPERATOR_ACTION_REQUIRED, operator-confirmed documentation-only
```

![BVLOS operator review UI](docs/assets/bvlos_screenshots/operator_review_ui.png)

![BVLOS mission overview](outputs/bvlos_powerline_inspection/mission_overview.png)

See the [BVLOS powerline demo script](docs/BVLOS_POWERLINE_DEMO_SCRIPT.md) for
the baseline feasibility, limiting constraint, what-if comparison, regulatory
readiness, and evidence bundle walkthrough. See the
[BVLOS demo screenshot set](docs/BVLOS_DEMO_SCREENSHOT_SET.md) for captured UI
dashboard, artifact navigation, trust / defensibility, Markdown dashboard,
audit, what-if, regulatory, index, and plot visuals with captions.

Evidence bundle quick checks do not rerun optimization:

```bash
python -m mission_framework.cli serve-ui
python -m mission_framework.cli open-first outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli verdict outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli top outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-summary outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-verify outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-top outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m mission_framework.cli bundle-review-validate outputs/bvlos_powerline_inspection/operator_evidence_bundle
```

`serve-ui` uses Python's built-in static file server to serve the generated
BVLOS demo bundle from
`outputs/bvlos_powerline_inspection/operator_evidence_bundle`. Open
`operator_review_ui.html` first for the lightweight local review surface; open
`operator_dashboard.md` first when reviewing the raw evidence artifacts. No
database, accounts, auth, build step, or manual file copying is required.

UI-first demo flow:

1. Regenerate the demo bundle with
   `python -m mission_framework.cli examples/bvlos_powerline_inspection_demo.yaml --outdir outputs --generated-at 2026-09-15T05:24:50Z`.
2. Launch the read-only local UI with `python -m mission_framework.cli serve-ui`
   and open the printed `operator_review_ui.html` URL.
3. Follow the review order strip: verdict, top constraint, trust signals,
   artifacts, then checksum. Scan the mission verdict, modeled status, risk,
   next operator action, readiness, completeness, weather evidence freshness,
   regulatory provenance, robustness, and evidence warnings in the compact
   desktop review stacks.
4. Use the Print / demo view button when preparing a customer-discovery PDF or
   archive printout. The print layout keeps review sections in readable order
   and uses compact artifact freshness columns to avoid large empty gaps.
5. Use the artifact links to open `operator_dashboard.md`,
   `inspection_constraint_audit.md`, `what_if_plan.md`, and
   `regulatory_readiness_report.md`. The Markdown, JSON, CSV, KML, PNG,
   manifest, checksum, and dashboard files remain accessible outside the UI;
   unavailable artifacts render as unavailable text rather than broken links.
6. Close with `python -m mission_framework.cli bundle-verify
   outputs/bvlos_powerline_inspection/operator_evidence_bundle`.

Live weather hooks and regulatory provenance fields are readiness records only
unless verified outside ORBITAL by the operator. ORBITAL does not grant
approval, authorization, LAANC, legal advice, or operational clearance.

The short commands mirror the dashboard language: `open-first` prints the first
artifact to open, `verdict` prints the mission verdict and next operator action,
and `top` prints the top limiting constraint with the recommended operator
action.

### Standard Domain Outputs

| Aircraft flight path | Spacecraft mission timeline |
| --- | --- |
| ![Aircraft flight path](outputs/aircraft/flight_path.png) | ![Spacecraft mission timeline](outputs/spacecraft/mission_timeline.png) |

| Aircraft battery state | Spacecraft operations summary |
| --- | --- |
| ![Aircraft battery state](outputs/aircraft/battery_state.png) | ![Spacecraft operations summary](outputs/spacecraft/operations_summary.png) |

---

## Project Artifacts

- Release notes: `docs/RELEASE_NOTES.md`
- Differentiation story: `docs/DIFFERENTIATION.md`
- Market proof: `docs/MARKET_PROOF.md`
- BVLOS demo narrative: `docs/BVLOS_POWERLINE_DEMO_SCRIPT.md`
- Primary BVLOS demo audit:
  `outputs/bvlos_powerline_inspection/inspection_constraint_audit.md`
  (includes model assumptions, margin units/sources, top-limiter rationale,
  reproducibility, and model limitations)
- BVLOS operator dashboard:
  `outputs/bvlos_powerline_inspection/operator_evidence_bundle/operator_dashboard.md`
- BVLOS evidence bundle summary:
  `outputs/bvlos_powerline_inspection/operator_evidence_bundle/evidence_bundle_summary.md`
- BVLOS demo screenshot set: `docs/BVLOS_DEMO_SCREENSHOT_SET.md`
- Technical report artifacts: `docs/`
- Results bundle: `outputs/`
- Reproducible outputs: `runs/` after executing `python run_all.py`

---

## Architecture Overview

```text
mission_framework/
  core/            Shared decision variables, constraints, objectives, planner
  simulation/      Feasibility, metrics, uncertainty utilities
  aircraft/        UAV mission model, dynamics, energy, wind, geofence checks
  spacecraft/      CubeSat orbit, visibility, attitude, power, scheduling
  reporting/       CSV and text output helpers
  visualization/   Aircraft and spacecraft plots
examples/          Demo YAML scenarios
tests/             Architecture, frame, and end-to-end tests
```

ORBITAL separates four concerns:

- Decision space: continuous, integer, binary, discrete, and permutation variables
- Simulation: aircraft dynamics, orbit propagation, battery models, and slew feasibility
- Constraints: hard constraints for feasibility and soft constraints for penalties
- Objective: minimize time/energy or maximize science value in a unified score space

---

## Baseline Comparisons

```bash
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml
```

Outputs:

```text
outputs/validation/baselines/
```

The report compares ORBITAL against `random_search`, `greedy_routing`, and
`earliest_deadline` baselines across score, feasibility, runtime, and robustness.
The current spacecraft demo is intentionally easy, so all spacecraft planners can
tie on full science value; see `docs/BASELINE_COMPARISONS.md` for benchmark scope
and current summarized results.

## Optimizer Maturity

```bash
python scripts/run_optimizer_maturity.py --out outputs/validation/optimizer_maturity/optimizer_maturity.csv --orbital-iterations 120 --orbital-restarts 1 --random-samples 25 --robustness-cases 3 --speed-grid 5 --offset-grid 3 --max-exhaustive-candidates 5000 --seed 0
```

Outputs:

```text
outputs/validation/optimizer_maturity/
```

This broader report adds stress scenarios and an `exhaustive_grid` solver-style
comparison where small decision spaces make enumeration practical. ORBITAL's
optimizer is strong demo and research engineering, but not yet production-grade
mission planning; see `docs/OPTIMIZER_MATURITY.md`.

---

## Stress Tests

```bash
python scripts/run_validation.py
```

Outputs:

```text
outputs/validation/
```

Failure cases are preserved for review.

---

## Multi-Seed Stability

```bash
python experiments/run_seed_experiments.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --seeds 20 --iterations 200 --restarts 1 --robustness 0 --out results/seed_runs.csv
```

---

## Expected Runtime

- Aircraft demo: about 30-60 seconds
- Spacecraft demo: about 60-120 seconds
- Full validation suite: about 10-15 minutes

During longer commands, `run_all.py` emits periodic progress updates and keeps
the full subprocess output in timestamped logs under `runs_logs/`.

---

## Development Checks

```bash
python scripts/focused_secret_scan.py
python -m mission_framework.cli ui-health outputs/bvlos_powerline_inspection/operator_evidence_bundle
python -m ruff check .
python -m black --check .
python -m mypy --python-version 3.12 mission_framework
python -m pytest
python -m pytest --cov=mission_framework --cov-report=term-missing
python run_all.py --fast --no-plots
```

Run the focused secret scan before any release tag or push. It checks the
release-facing README, docs, examples, and BVLOS demo outputs for high-signal
credential patterns.

---

## License

MIT License  
Copyright (c) 2026 Rebecca Shillingford
