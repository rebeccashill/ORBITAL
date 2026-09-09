# Release Notes

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
