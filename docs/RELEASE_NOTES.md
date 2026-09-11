# Release Notes

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
