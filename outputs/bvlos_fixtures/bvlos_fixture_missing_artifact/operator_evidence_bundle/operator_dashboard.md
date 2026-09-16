# ORBITAL Operator Evidence Dashboard

## Mission Verdict: REVIEW REQUIRED

Modeled feasibility is acceptable, but operator, regulatory, or evidence review items remain.

**Next action:** Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision.

## 30-Second Review Path

Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum.

**First artifact to open:** [operator_dashboard.md](operator_dashboard.md) (this file).

| Step | Open / verify |
| --- | --- |
| Verdict | REVIEW REQUIRED - Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision. |
| Top constraint | Wind / weather margin, PASS, margin 3.6 m/s |
| Checksum / freshness | VERIFY REQUIRED; generated 2026-09-15T05:24:50Z; manifest version 1 |
| Trust signals | Weather evidence, regulatory provenance, robustness, model assumptions, and evidence warnings. |
| Artifacts | Open raw Markdown, JSON, CSV, KML, plots, manifest, and checksum links below. |
| Checksum | Run bundle checksum verification before archiving or sharing. |

## Raw Evidence Quick Links

| Type | Links |
| --- | --- |
| Raw Markdown | [operator_dashboard.md](operator_dashboard.md); [inspection_constraint_audit.md](inspection_constraint_audit.md); [what_if_plan.md](what_if_plan.md); [regulatory_readiness_report.md](regulatory_readiness_report.md); [evidence_bundle_summary.md](evidence_bundle_summary.md); [artifact_index.md](artifact_index.md) |
| JSON Evidence | [plan.json](plan.json); [inspection_constraint_audit.json](inspection_constraint_audit.json); [what_if_plan.json](what_if_plan.json); [regulatory_readiness_report.json](regulatory_readiness_report.json); [score_breakdown.json](score.json); [weather_snapshot.json](weather.json); robustness_summary.json unavailable (missing: robustness.json) |
| CSV / KML | [autopilot_mission.csv](autopilot_mission.csv); [mission_review.kml](mission_review.kml) |
| Plots | [flight_path.png](flight_path.png) |
| Manifest / checksum | [manifest.json](manifest.json); [checksum_manifest.json](checksum_manifest.json) |

## Manifest Compatibility

| Contract | Value |
| --- | --- |
| Manifest version | 1 |
| UI schema version | 1 |
| Required UI-facing top-level fields | 15 expected |
| Optional UI fallbacks | 15 documented |
| Outside-UI access | yes |
| Unavailable artifact policy | Unavailable artifacts render as non-link unavailable labels in the review UI and Markdown dashboard; they must not be emitted as hrefs. |

Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts remain accessible outside the UI. Unavailable artifacts are rendered as unavailable text, not links.

## Why This Verdict?

The verdict is REVIEW REQUIRED because modeled feasibility is GO but regulatory readiness, missing evidence, or bundle warnings still need operator attention.

| Verdict input | Current value | Derivation rule |
| --- | --- | --- |
| Modeled mission status | GO | MODIFY if not GO. |
| Regulatory readiness | DOCUMENTED_REVIEW_REQUIRED | REVIEW REQUIRED when OPERATOR_ACTION_REQUIRED. |
| Missing evidence | 1 item(s) | REVIEW REQUIRED when greater than 0. |
| Bundle warnings | 1 warning(s) | REVIEW REQUIRED when greater than 0. |

## Model Assumptions Snapshot

| Area | Summary | Operator should verify |
| --- | --- | --- |
| Battery / energy model | Battery feasibility is based on the configured capacity, initial charge, reserve policy, and simplified power model coefficients. | Confirm aircraft battery health, payload draw, temperature effects, and abort reserve outside ORBITAL before release. |
| Wind / weather model | Wind feasibility compares the modeled or weather-provided wind exposure against the configured safe operating limit. | Refresh field weather and gust observations close to launch, especially when offline or sample weather is used. |
| Geofence / no-fly-zone model | Geofence feasibility treats configured polygons and imported GeoJSON zones as the planning boundary source. | Confirm site boundaries, customer buffers, and launch/recovery areas on current maps before export or dispatch. |

## Mission Card

| Field | Value |
| --- | --- |
| Mission | BVLOS Missing Artifact Fixture |
| Verdict | REVIEW REQUIRED |
| Modeled mission status | GO |
| Mission risk | LOW |
| Top limiting constraint | Wind / weather margin, PASS, margin 3.6 m/s |
| Regulatory readiness | DOCUMENTED_REVIEW_REQUIRED |
| Evidence completeness | 94.1 % (16 / 17 artifacts present) |
| Weather evidence status | PACKAGED |
| Weather source | Operator-packaged field weather observation |
| Weather timestamp | 2026-09-15T05:15:00Z |
| Weather freshness | packaged |
| Regulatory provenance | DOCUMENTED |
| Regulatory date checked | 2026-09-15T04:30:00Z |
| Regulatory expiration | 2026-12-31 |
| Checksum evidence | VERIFY REQUIRED |
| Robustness status | No robustness cases were recorded for this bundle. Confidence from uncertainty testing is not estimated. |
| Evidence warning status | REVIEW REQUIRED: 1 missing artifact(s), 0 stale artifact(s), 1 missing evidence item(s), 1 bundle warning(s) |
| Missing evidence | 1 item(s) |
| Bundle warnings | 1 warning(s) |

## Decision-Support Boundary

ORBITAL provides decision support only: not approval, not authorization, not legal advice, not LAANC, and not operational clearance. The pilot-in-command and operator retain final responsibility for release.

## 10-Second Mission Read

| Signal | Current value | Operator cue |
| --- | --- | --- |
| Verdict | REVIEW REQUIRED | Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision. |
| Modeled mission status | GO | Use as the first feasibility read from the constraint audit. |
| Mission risk | LOW | Treat higher risk as a cue for additional operator review. |
| Top limiting constraint | Wind / weather margin, PASS, margin 3.6 m/s | Review this constraint before changing or releasing the mission. |
| Regulatory readiness | DOCUMENTED_REVIEW_REQUIRED | Confirm required approvals, waivers, roles, and restrictions outside ORBITAL. |
| Evidence completeness | 94.1 % (16 / 17 artifacts present) | Confirm expected artifacts are present before sharing. |
| Regulatory documentation completeness | 100.0 % (11 / 11 fields documented) | Confirm optional evidence fields are documented where needed. |
| Weather evidence | PACKAGED: packaged weather evidence from Operator-packaged field weather observation. Confirm it against launch-time field conditions. Timestamp: 2026-09-15T05:15:00Z. | Confirm packaged weather evidence against launch-time field conditions. Operator should verify the source outside ORBITAL. |
| Regulatory provenance | DOCUMENTED: regulatory evidence is documented for review. Source: Operator planning record; checked: 2026-09-15T04:30:00Z; expiration: 2026-12-31; authority: Operator internal review; confirmation: not_required. | Keep source, date checked, expiration, and confirmation record with the bundle. Operator should verify regulatory inputs. |
| Checksum evidence | Checksum manifest is generated with the bundle; verification must be run against the final archived files. | Run bundle checksum verification after generation and before archiving or sharing the evidence bundle. |
| Uncertainty / robustness | No robustness cases were recorded for this bundle. Confidence from uncertainty testing is not estimated. | Run robustness cases when uncertainty or margin sensitivity matters. |
| Evidence warnings | REVIEW REQUIRED: 1 missing artifact(s), 0 stale artifact(s), 1 missing evidence item(s), 1 bundle warning(s) | Check stale, missing, or mismatched evidence before archiving. |

## Trust And Defensibility

### Sample Data / Demo Scenario Note

Scenario data note: verify route, weather, regulatory, crew, and customer evidence before operational use. Operator should verify source inputs.

### Model Assumptions Summary

| Area | Summary | Operator check |
| --- | --- | --- |
| Battery / energy model | Battery feasibility is based on the configured capacity, initial charge, reserve policy, and simplified power model coefficients. | Confirm aircraft battery health, payload draw, temperature effects, and abort reserve outside ORBITAL before release. |
| Wind / weather model | Wind feasibility compares the modeled or weather-provided wind exposure against the configured safe operating limit. | Refresh field weather and gust observations close to launch, especially when offline or sample weather is used. |
| Geofence / no-fly-zone model | Geofence feasibility treats configured polygons and imported GeoJSON zones as the planning boundary source. | Confirm site boundaries, customer buffers, and launch/recovery areas on current maps before export or dispatch. |
| Route completion model | The route is considered complete only when the simulation reaches the required inspection waypoints under the configured reach radius. | Confirm the waypoint list matches the inspection scope and define any acceptable skipped-point policy before dispatch. |
| Turn / bank feasibility model | Turn feasibility uses a simplified bank-angle/yaw-rate envelope rather than aircraft-specific autopilot tracking or detailed aerodynamics. | Confirm the route geometry, turn spacing, and selected speed are within the aircraft operating envelope. |
| Robustness model | Robustness reflects configured Monte Carlo perturbations only; it is not a certification, reliability guarantee, or live safety monitor. | Increase robustness cases or add scenario-specific uncertainty ranges when margin sensitivity matters. |

### Known Limitations Summary

| Limitation | Applies | Operator meaning |
| --- | --- | --- |
| offline_sample_weather | yes | Weather may come from offline, fallback, or sample inputs. ORBITAL records the source and timestamp, but the operator must verify current field weather before release. |
| simplified_flight_dynamics | yes | Aircraft dynamics are simplified for feasibility planning. ORBITAL does not model every autopilot behavior, controller response, payload effect, battery aging factor, sensor constraint, or emergency maneuver. |
| decision_support_only | yes | Constraint margins are planning evidence for operator review. They do not approve a flight, issue authorization, or replace pilot-in-command judgment. |

### Evidence Warnings At A Glance

| Signal | Value |
| --- | --- |
| Status | REVIEW REQUIRED |
| Missing artifacts | 1 |
| Stale artifacts | 0 |
| Missing evidence items | 1 |
| Bundle warnings | 1 |

### Stale / Missing / Mismatched Evidence Scan

| Signal | Count |
| --- | --- |
| Stale artifacts | 0 |
| Missing artifacts | 1 |
| Mismatched artifacts | 0 |
| Missing evidence items | 1 |
| Bundle warnings | 1 |

Scan summary: 0 stale, 1 missing, 0 mismatched, 1 missing evidence item(s), 1 warning(s).

### Artifact Freshness Summary

| Artifact | Status | Source timestamp | Bundle timestamp | Operator should verify |
| --- | --- | --- | --- | --- |
| Scenario YAML | CURRENT | 2026-09-16T04:57:45Z | 2026-09-16T04:57:45Z | Verify source timestamp and checksum before archiving. |
| Primary constraint-audit report | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| Regulatory readiness report | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| What-if planning report | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| Weather snapshot | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| Autopilot mission CSV | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| Mission review KML | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |
| Flight-planning exports manifest | CURRENT | 2026-09-15T05:24:50Z | 2026-09-15T05:24:50Z | Verify source timestamp and checksum before archiving. |

Open `evidence_bundle_summary.md`, `manifest.json`, and `checksum_manifest.json` when any warning count is nonzero.

## Recommended Opening Sequence

1. Start here with the dashboard.
2. Open the primary constraint audit for feasibility and top-limiter rationale.
3. Open the what-if plan to see how mission changes affect feasibility.
4. Open regulatory readiness to confirm documentation-only action items.
5. Open the manifest, artifact index, and checksum manifest before archiving.

## Mission Snapshot

- Mission: BVLOS Missing Artifact Fixture
- Mission verdict: REVIEW REQUIRED
- Mission status: GO
- Mission risk: LOW
- Top limiting constraint: Wind / weather margin, PASS, margin 3.6 m/s
- Regulatory readiness: DOCUMENTED_REVIEW_REQUIRED
- Bundle completeness: 94.1 % (16 / 17 artifacts present)
- Regulatory documentation completeness: 100.0 % (11 / 11 fields documented)
- Missing evidence items: 1
- Bundle warnings: 1

## Operator Review

Review status: draft
Reviewer name: Fixture reviewer
Review timestamp UTC: 2026-09-15T05:24:50Z
Operator decision: pending operator review
Review notes: Fixture with robustness disabled so the expected robustness artifact is unavailable.

| Field | Value |
| --- | --- |
| Review status | draft |
| Reviewer name | Fixture reviewer |
| Review timestamp UTC | 2026-09-15T05:24:50Z |
| Operator decision | pending operator review |
| Review notes | Fixture with robustness disabled so the expected robustness artifact is unavailable. |

Review fields are documentation-only records; they do not change release authority.

## Artifact Shortcuts

### Feasibility And Decision Support

| Artifact | Link |
| --- | --- |
| Primary constraint audit | [inspection_constraint_audit.md](inspection_constraint_audit.md) |
| What-if plan | [what_if_plan.md](what_if_plan.md) |
| Regulatory readiness | [regulatory_readiness_report.md](regulatory_readiness_report.md) |

### Evidence Package

| Artifact | Link |
| --- | --- |
| Bundle manifest | [manifest.json](manifest.json) |
| Checksum manifest | [checksum_manifest.json](checksum_manifest.json) |
| Artifact index | [artifact_index.md](artifact_index.md) |

### Route, Export, And Field-Use Artifacts

| Artifact | Link |
| --- | --- |
| Flight path plot | [flight_path.png](flight_path.png) |
| Autopilot CSV | [autopilot_mission.csv](autopilot_mission.csv) |
| Mission review KML | [mission_review.kml](mission_review.kml) |

## Missing Evidence

- Robustness summary (artifact, robustness.json): Expected evidence artifact is missing from the bundle.

## Bundle Warnings

- missing_artifact: Expected evidence artifact is missing from the bundle.

## Next Operator Actions

- Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision.
- Review the primary constraint audit and top limiting constraint.
- Review the what-if plan if any constraint margin is tight.
- Verify bundle completeness, manifest, and checksum manifest before archiving.
- Record reviewer, timestamp, notes, and operator decision in scenario metadata when appropriate.
