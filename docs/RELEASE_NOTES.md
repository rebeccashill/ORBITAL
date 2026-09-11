# Release Notes

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
- Regenerated the BVLOS powerline inspection output bundle with the new audit
  artifacts.

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
