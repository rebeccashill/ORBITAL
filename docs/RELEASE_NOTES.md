# Release Notes

## v1.0.13 - September 13, 2026

### Changed

- Refreshed the README, BVLOS demo script, and screenshot set around the
  v1.0.13 operator review flow.
- Added a short "what improved since v1.0.12" narrative focused on the
  30-second review path, why-this-verdict explanation, manifest compatibility,
  checksum readiness, freshness scanning, and raw evidence accessibility.
- Reframed the screenshot captions around the premium review UI: verdict, top
  constraint, trust signals, source artifacts, checksum evidence, and
  trust/defensibility panels.
- Added customer-discovery demo language for credibility and operator trust,
  including prompts for how customers verify weather, regulatory provenance,
  stale artifacts, route exports, and checksum evidence today.
- Made the live weather and regulatory boundary explicit: live/regulatory
  fields are documentation-only readiness records unless verified outside
  ORBITAL by the operator, and ORBITAL does not grant approval, authorization,
  LAANC, legal advice, or operational clearance.
- Expanded release-hardening tests for manifest schema compatibility, stale
  weather/regulatory warnings, freshness and provenance rendering, all verdict
  derivation paths, UI screenshot anchor targets, generated UI smoke coverage,
  and the checksum-verification release gate.
- Bumped package and README release metadata to `v1.0.13`.

### Verified

- Refreshed the committed operator review UI screenshots and checked them for
  nonblank rendered content.
- Regenerated `outputs/bvlos_powerline_inspection/`.
- Ran `python -m black --check .`.
- Ran `python -m ruff check .`.
- Ran `python -m mypy --python-version 3.12 mission_framework`.
- Ran `python -m pytest` with 99 passing tests.
- Ran `python run_all.py --fast --no-plots`.
- Ran `python -m mission_framework.cli bundle-verify outputs\bvlos_powerline_inspection\operator_evidence_bundle`.
- Ran `python -m mission_framework.cli bundle-review-validate outputs\bvlos_powerline_inspection\operator_evidence_bundle`.
- Ran `python scripts/focused_secret_scan.py`.
- Ran `git diff --check`.

## v1.0.12 - September 13, 2026

### Changed

- Finished the lightweight read-only operator review web UI for BVLOS evidence
  bundles.
- Made the first screen emphasize mission verdict, modeled status, risk, top
  limiting constraint, next operator action, regulatory readiness, evidence
  completeness, regulatory documentation completeness, weather evidence
  readiness, regulatory provenance, checksum readiness, robustness /
  uncertainty, missing evidence count, and stale / missing / mismatched evidence
  warning count.
- Added operational evidence readiness fields for live, fallback, sample,
  stale, packaged, and missing weather evidence, plus documentation-only
  regulatory provenance fields for source, date checked, expiration, authority,
  and operator confirmation status.
- Added trust / defensibility panels for why-the-verdict derivation, near-fold
  model assumptions, robustness confidence language, operator-verify cues,
  artifact freshness timestamps, and stale / missing / mismatched evidence
  scanning.
- Added compact review sections for feasibility, regulatory readiness, evidence
  completeness, trust / defensibility, warnings, artifact navigation, and
  operator review metadata.
- Completed evidence bundle navigation with links to the dashboard, audit,
  what-if, regulatory, summary, index, manifest, checksum, route image, CSV,
  and KML artifacts, including an obvious open-first dashboard callout and
  unavailable states for missing artifacts.
- Added static manifest loading from `manifest.json`, with an embedded fallback
  snapshot and graceful status messages for missing or malformed manifest data.
- Added a one-command local launch path with `serve-ui`, backed by Python's
  built-in static file server and the generated BVLOS demo bundle.
- Updated README and BVLOS demo documentation with a UI-first launch flow,
  read-only/source-of-truth boundary language, and refreshed UI dashboard,
  artifact-navigation, and trust/defensibility screenshots.
- Tightened the review UI visual style with compact mission cards, clearer
  verdict/status/warning styling, neutral documentation-only fields, and
  restrained laptop/tablet-friendly layout.
- Added stronger local-review, decision-support-only, source-of-truth, demo /
  discovery, and no-approval-workflow boundary language above the fold.
- Regenerated `outputs/bvlos_powerline_inspection/` and its operator evidence
  bundle for the v1.0.12 UI, launch, screenshot, and checksum workflow.
- Bumped package and README release metadata to `v1.0.12`.

### Verified

- Ran `python -m black --check .`.
- Ran `python -m ruff check .`.
- Ran `python -m mypy --python-version 3.12 mission_framework`.
- Ran `python -m pytest`.
- Ran `python run_all.py --fast --no-plots`.
- Ran `python scripts/focused_secret_scan.py`.
- Ran `python -m mission_framework.cli bundle-verify outputs\bvlos_powerline_inspection\operator_evidence_bundle`.

## v1.0.11 - September 13, 2026

### Changed

- Polished the operator dashboard so the mission verdict, risk, top limiting
  constraint, regulatory readiness, evidence completeness, weather fallback
  status, robustness status, and evidence warning status are visible in the
  first review surface.
- Added trust and defensibility signals to the evidence workflow, including a
  model assumptions summary, known limitations summary, sample-data / demo
  scenario note, weather fallback status, uncertainty / robustness status, and
  stale or missing evidence warning summary.
- Improved the evidence bundle review flow with clearer README, artifact index,
  review, archive, completeness, and checksum language.
- Added short CLI demo commands and README examples for opening the first
  artifact, printing the mission verdict, and printing the top limiting
  constraint.
- Tightened README positioning with a sharper one-liner, audience, problem,
  generic-tool gap, why-now, and decision-support-not-approval sections.
- Added a committed BVLOS screenshot gallery and refreshed the dashboard
  screenshot to show the new trust signals.
- Added `scripts/focused_secret_scan.py` and documented it as a required
  release check before tagging or pushing.
- Regenerated the BVLOS powerline inspection evidence bundle for the v1.0.11
  dashboard and trust/defensibility workflow.
- Bumped package and README release metadata to `v1.0.11`.

### Verified

- Added focused formatter and end-to-end coverage for the changed dashboard,
  evidence summary, manifest trust metadata, and evidence bundle behavior.
- Ran `python -m black --check .`.
- Ran `python -m ruff check .`.
- Ran `python -m mypy --python-version 3.12 mission_framework`.
- Ran `python -m pytest`.
- Ran `python run_all.py --fast --no-plots`.
- Ran `python scripts/focused_secret_scan.py`.
- Ran `python -m mission_framework.cli bundle-verify outputs\bvlos_powerline_inspection\operator_evidence_bundle`.

## v1.0.10 - September 12, 2026

### Changed

- Improved the operator evidence dashboard visual hierarchy with a
  10-second mission read, at-a-glance status table, recommended opening
  sequence, grouped artifact shortcuts, and clearer operator review metadata.
- Made mission status, mission risk, top limiting constraint, regulatory
  readiness, bundle completeness, missing evidence, and bundle warnings
  scannable at the top of the dashboard.
- Improved the human-readable evidence bundle summary with a reviewer snapshot,
  recommended review flow, clearer completeness breakdown, and direct links to
  dashboard, audit, what-if, regulatory, manifest, and checksum artifacts.
- Made the constraint-audit Markdown more operator-friendly with an operator
  handoff table and a constraint summary that explains what ORBITAL checked,
  why it matters, and the recommended operator action.
- Added a recommended opening order to the artifact index and bundle README.
- Added `docs/BVLOS_DEMO_SCREENSHOT_SET.md` for polished demo screenshot and
  artifact capture planning.
- Updated README and BVLOS demo script sample output to use the dashboard-first
  v1.0.10 UX flow.
- Bumped package metadata to `v1.0.10`.

### Verified

- Added formatter, CLI, and end-to-end coverage for the refreshed dashboard,
  evidence summary, artifact index, and generated BVLOS evidence workflow.
- Regenerated the BVLOS powerline inspection outputs for the v1.0.10 dashboard
  and screenshot-set workflow.

## v1.0.9 - September 12, 2026

### Changed

- Added an operator evidence dashboard as the first evidence-bundle artifact to
  open, summarizing mission status, mission risk, top limiting constraint,
  regulatory readiness, bundle completeness, review fields, and artifact links.
- Added documentation-only operator review notes and operator decision fields to
  evidence bundle metadata.
- Included what-if planning artifacts in the operator evidence bundle so the
  dashboard can link directly to audit, what-if, regulatory, manifest, checksum,
  plot, CSV, and KML artifacts.
- Added artifact freshness metadata to evidence bundle manifests, including
  generated timestamp, scenario SHA-256, ORBITAL version, and command used.
- Added checksum verification helper support for evidence bundles, including
  checksum, file-size, and bundled-scenario hash checks.
- Added bundle warnings for missing, stale, and scenario-mismatched evidence
  artifacts.
- Added non-blocking scenario validation warnings for expired authorization
  documentation, missing or malformed operating windows, altitude-limit
  mismatches, stale weather timestamps, and missing emergency / contingency
  plan documentation, and surfaced that emergency plan note in regulatory
  evidence metadata.
- Added model transparency to inspection constraint audits, including
  assumptions for battery, wind, geofence, route completion, turn feasibility,
  and robustness; margin units and sources; top-limiter selection rationale;
  reproducibility metadata; and model limitation language.
- Added read-only evidence bundle CLI commands for bundle summaries, checksum
  verification, top-limiting-constraint review, and review metadata validation,
  plus default run output that points users to the first artifact to open.
- Refreshed the BVLOS powerline inspection demo outputs and demo script around
  the v1.0.9 operator-dashboard-first evidence workflow.
- Preserved the artifact completeness score while reporting regulatory
  documentation completeness separately in machine-readable and human-readable
  bundle outputs.
- Clarified dashboard and review-field language: not approval, not
  authorization, not legal advice, not LAANC, and not operational clearance.

## v1.0.8 - September 12, 2026

This documentation release sharpens ORBITAL's product differentiation as a
constraint-aware BVLOS inspection feasibility and audit evidence layer.

### Changed

- Added `docs/DIFFERENTIATION.md` with ORBITAL's category definition,
  product-boundary narrative, comparison table, differentiation pillars, and
  HBS-ready positioning paragraph.
- Added `docs/MARKET_PROOF.md` with the inspection-operator problem statement,
  buyer and user assumptions, target customer profiles, and top alternatives
  that clarify why ORBITAL differs from generic planning tools.
- Added `docs/BVLOS_POWERLINE_DEMO_SCRIPT.md` with a presenter-ready demo
  narrative for the BVLOS powerline inspection scenario, covering baseline
  feasibility, the top limiting constraint, what-if comparison, regulatory
  readiness, final evidence bundle, and README-ready sample outputs.
- Clarified that ORBITAL's core operator question is: "Can we safely and
  defensibly fly this mission?"
- Explained how ORBITAL differs from generic route planners, fleet tools,
  autopilots, LAANC providers, and GIS viewers.
- Made the constraint-audit report the primary BVLOS demo artifact, with
  pass / warning / fail constraint groups, plain-English explanations, operator
  impact language, and recommended actions.
- Added what-if before/after improvement summaries when an alternative improves
  feasibility or audit margins.
- Included the Markdown constraint-audit report in the operator evidence bundle.
- Added evidence bundle summary and artifact index pages, a completeness score,
  a combined missing-evidence list, documentation-only operator review status,
  optional reviewer fields, and a lightweight SHA-256 checksum manifest.
- Updated README release metadata and project artifact links for `v1.0.8`.
- Bumped package metadata to `v1.0.8`.

### Verified

- Added version metadata coverage for `v1.0.8`.
- Added focused coverage for evidence bundle completeness scoring and evidence
  artifact index generation.
- Added end-to-end coverage for the enhanced constraint-audit workflow and
  what-if improvement summaries.
- Added end-to-end and CLI coverage for evidence bundle summary, index,
  completeness, missing evidence, review status, and checksums.
- Added CLI end-to-end coverage that the BVLOS demo generates baseline plan,
  score, and constraint artifacts plus audit, what-if, regulatory readiness, and
  evidence bundle artifacts.
- Ran `python -m pytest`, `python -m ruff check .`,
  `python -m mypy --python-version 3.12 mission_framework`, and
  `python run_all.py --fast --no-plots`.

## v1.0.7 - September 11, 2026

This patch release adds a dedicated regulatory readiness report for aircraft /
BVLOS inspection planning while preserving ORBITAL's role as decision support,
not an approval system.

### Changed

- Added `regulatory_readiness_report.json` and
  `regulatory_readiness_report.md` for aircraft runs.
- Summarized LAANC-required status, waiver / authorization-required status,
  airspace class, visual observer requirements, and ground-risk / population
  notes in a dedicated regulatory artifact.
- Added operating assumptions and unresolved regulatory items to the report,
  with optional scenario fields for operator-provided assumptions and action
  items.
- Added an operator-facing approval checklist with conditional LAANC, waiver /
  authorization, and visual observer confirmations plus crew briefing,
  emergency / contingency plan, NOTAM / local restriction, weather minimums, and
  battery reserve confirmation items.
- Added optional documentation-only regulatory evidence fields for authorization
  ID/reference, approving authority/source, expiration date, operating altitude
  limit, operating time window, required crew roles, and special conditions /
  limitations.
- Added non-blocking validation warnings for incomplete BVLOS regulatory
  metadata, missing authorization references when required, and missing visual
  observer crew-role documentation.
- Included an explicit disclaimer that ORBITAL provides decision support only
  and is not legal approval.
- Added the regulatory readiness report, approval checklist summary, regulatory
  metadata, and documentation-only missing-evidence status to the operator
  evidence bundle manifest and README.
- Bumped package and README release metadata to `v1.0.7`.

### Verified

- Added validation coverage for regulatory evidence fields, assumptions,
  unresolved-item lists, and non-blocking warning behavior.
- Added unit coverage for regulatory readiness report JSON/Markdown content,
  evidence fields, disclaimers, and approval checklist behavior.
- Added CLI and end-to-end coverage for automatic regulatory report generation,
  artifact writing, evidence-bundle inclusion, approval checklist manifest data,
  and missing regulatory evidence visibility.

## v1.0.6 - September 11, 2026

This patch release connects the BVLOS planning workflow to operational weather,
GIS, downstream export, and fleet-readiness inputs while preserving deterministic
offline demos.

### Changed

- Added a weather provider layer with offline/mock snapshots and an Open-Meteo
  live provider integration.
- Added scenario weather fields for provider, timestamp, location, forecast
  window, fallback behavior, and operational wind limits.
- Mapped resolved weather wind speed/direction/gusts into the existing aircraft
  wind model before planning.
- Added weather source, timestamp, fallback status, visibility, precipitation,
  temperature, and gust data to the drone inspection audit.
- Added weather metadata and `weather.json` to the operator evidence bundle.
- Added GeoJSON route and geofence imports for aircraft scenarios, including
  LineString/MultiLineString asset routes and Polygon/MultiPolygon no-fly zones.
- Added BVLOS example GeoJSON files for the powerline route and substation
  no-fly zone.
- Added opt-in downstream flight-planning exports with a simple autopilot
  mission CSV, KML route review file, and planning-only disclaimer.
- Included downstream export artifacts in the operator evidence bundle when
  enabled.
- Added optional enterprise mission metadata and fleet metadata fields for
  operator, aircraft, pilot, organization, asset owner, drone model, battery
  pack, sensor payload, and inspection type.
- Added a `batch` CLI entry point that runs multiple inspection scenarios and
  writes CSV/Markdown summaries with status, risk, top constraint, and evidence
  path.

### Verified

- Added unit tests for mock/offline weather mapping and Open-Meteo payload
  parsing.
- Added validation coverage for the new weather scenario fields.
- Added validation coverage for malformed or empty GeoJSON route/geofence files.
- Added tests for GeoJSON geofence import.
- Added end-to-end coverage for autopilot CSV/KML exports and evidence-bundle
  inclusion.
- Added tests for KML/CSV export generation.
- Added validation, report, memo, and batch-summary coverage for enterprise /
  fleet readiness fields.
- Added end-to-end coverage for the BVLOS demo with mock weather, GeoJSON route
  and geofence inputs, weather metadata in the audit, and evidence artifacts.
- Ran pytest, Ruff, mypy for `mission_framework`, and the fast no-plot demo
  runner locally.

## v1.0.5 - September 11, 2026

This patch release makes the HBS BVLOS inspection positioning more defensible by
adding a dedicated drone inspection constraint-audit report.

### Changed

- Added `inspection_constraint_audit.json` and `inspection_constraint_audit.md`
  for aircraft/drone inspection runs.
- Reported battery reserve margin, wind/weather margin, geofence/no-fly-zone
  clearance, route completion, and turn/bank feasibility in one operator-facing
  audit.
- Added top limiting constraint, low/medium/high mission risk, and top three
  risk drivers to the audit payload.
- Added configurable wind audit thresholds through `wind.max_safe_wind_mps` and
  `wind.warning_margin_mps`.
- Added opt-in BVLOS what-if planning artifacts that compare fewer waypoints,
  lower speed, alternate launch point, stronger wind, larger battery reserve, and
  relaunch / battery swap options.
- Added documentation-only regulatory metadata fields for LAANC, waiver /
  authorization, airspace class, visual observer requirements, and
  ground-risk/population notes.
- Added an operator evidence bundle with the scenario YAML, plan JSON,
  constraint audit JSON, score breakdown, flight path plot, robustness summary,
  and plain-English go/no-go memo.
- Regenerated the BVLOS powerline inspection output bundle with the new audit
  and what-if artifacts.

### Verified

- Added end-to-end test coverage for the drone inspection audit report.
- Validated the BVLOS scenario with the new wind audit fields.
- Ran pytest, Ruff, mypy for `mission_framework`, and the fast no-plot demo
  runner locally.

## v1.0.4 - September 11, 2026

This patch release narrows ORBITAL's venture story around constraint-aware BVLOS
inspection planning while preserving the existing unified aircraft and
spacecraft mission-planning architecture.

### Changed

- Repositioned the README around the BVLOS inspection wedge: battery, weather,
  geofence, route-completion, and regulatory-adjacent preflight decision
  support.
- Added `examples/bvlos_powerline_inspection_demo.yaml`, a fixed-order powerline
  corridor inspection scenario with six tower waypoints, sinusoidal wind,
  geofence clearance, and a battery reserve requirement.
- Added optional aircraft `vehicle.battery_reserve_Wh` support and a
  `battery_reserve` hard constraint without changing the existing
  `battery_nonnegative` contract.
- Added optional `mission.fixed_order` support so linear-asset demos can preserve
  corridor order while the default aircraft planner still supports waypoint
  permutation.
- Added safe `output.run_dir_name` validation so curated demos can write stable
  output bundle paths.
- Added a lightweight BVLOS operator memo with go/no-go status, top constraints,
  robustness summary, and recommended next actions.
- Updated optimizer maturity exhaustive-grid assignment generation to respect
  fixed-order aircraft scenarios.

### Verified

- Added validation coverage for the BVLOS powerline inspection scenario.
- Added an aircraft end-to-end smoke test for the new BVLOS demo.
- Generated `outputs/bvlos_powerline_inspection/` with waypoint CSV, stable JSON
  artifacts, plots, and `operator_memo.md`.
- Ran pytest, Ruff, mypy for `mission_framework`, and the fast no-plot demo
  runner locally.

## v1.0.3 - September 10, 2026

This patch release focuses on credibility and polish gaps in the ORBITAL 1.0
artifact set.

### Changed

- Regenerated the archived aircraft output bundle so docs, plots, logs, and
  JSON artifacts consistently describe a feasible run.
- Added strict JSON serialization helpers and routed CLI/reporting JSON writes
  through them so `NaN`, `Infinity`, and `-Infinity` cannot be emitted silently.
- Enforced spacecraft target `time_windows` by default by intersecting declared
  UTC target windows with computed visibility windows before scheduling
  observations.
- Regenerated the checked-in spacecraft output bundle with strict JSON artifacts
  and the new `target_time_windows` hard constraint.
- Reframed spacecraft baseline results as an intentionally easy smoke benchmark
  and documented the current proxy-based model limitations.
- Added an optimizer maturity benchmark covering demo and stress scenarios,
  including an `exhaustive_grid` solver-style comparison where enumeration is
  practical.
- Documented that the current optimizer is strong demo/research engineering, but
  not yet production-grade mission planning.

### Verified

- Validated bundled spacecraft demo and stress YAML files.
- Reran baseline comparison artifacts with documented parameters.
- Generated optimizer maturity CSV and Markdown artifacts with demo and stress
  scenarios.
- Ran Black, Ruff, mypy, pytest, and strict JSON artifact scans locally.

## v1.0.2 - September 9, 2026

This patch release refreshes reproducibility, packaging, and release artifact
evidence for the ORBITAL 1.0 line.

### Changed

- Cleaned user-facing documentation and validation console banners for portable
  text rendering.
- Verified and documented CLI reproducibility for seeded runs, option overrides,
  custom output directories, and Windows PowerShell readability.
- Added hidden single-dash CLI compatibility aliases for checklist-style command
  variants such as `-seed`, while keeping standard `--seed` documentation.
- Regenerated baseline comparison CSV and Markdown artifacts with the documented
  parameters.
- Documented that baseline runtimes are machine-dependent while score,
  feasibility, and robust pass rates are deterministic checks.
- Added `build/`, `dist/`, and `.venv*/` ignore rules for packaging hygiene.
- Stopped tracking generated egg-info metadata; installs and builds regenerate it
  locally.
- Enabled CI runs for `v*` tag pushes.

### Verified

- Confirmed Python 3.10 editable install works in `.venv310`.
- Confirmed imports and the `orbital` console script work outside the repository
  root.
- Built source and wheel distributions and inspected archive contents for cache
  files or missing package data.
- Ran Black, Ruff, mypy, pytest, coverage, baseline refresh, and smoke checks
  before tagging.

## v1.0.1 - September 9, 2026

This patch release tightens release metadata and validation coverage for the
ORBITAL 1.0 line.

### Changed

- Bumped package metadata from `1.0.0` to `1.0.1`.
- Added package-level `mission_framework.__version__`.
- Updated README release metadata to reference `v1.0.1`.
- Fixed the stress validation inventory path for
  `examples/stress/spacecraft_slew-constrained.yaml`.

### Verified

- Confirmed the `orbital` console script installs and runs scenario validation.
- Validated both demo YAML files and every stress YAML file.
- Added tests for version metadata and stress scenario inventory.
- Ran Black, Ruff, mypy, and pytest before tagging.
