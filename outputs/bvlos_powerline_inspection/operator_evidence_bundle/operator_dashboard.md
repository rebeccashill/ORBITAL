# ORBITAL Operator Evidence Dashboard

## Mission Verdict: REVIEW REQUIRED

Modeled feasibility is acceptable, but operator, regulatory, or evidence review items remain.

**Next action:** Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision.

## Mission Card

| Field | Value |
| --- | --- |
| Mission | BVLOS Powerline Inspection Demo |
| Verdict | REVIEW REQUIRED |
| Modeled mission status | GO |
| Mission risk | LOW |
| Top limiting constraint | Wind / weather margin, PASS, margin 3.1 m/s |
| Regulatory readiness | OPERATOR_ACTION_REQUIRED |
| Evidence completeness | 100.0 % (17 / 17 artifacts present) |
| Weather fallback status | FALLBACK USED |
| Robustness status | PASS: 20 case(s), hard pass rate 100.0 %, worst hard margin 0.139 |
| Evidence warning status | CLEAR: 0 missing artifact(s), 0 stale artifact(s), 0 missing evidence item(s), 0 bundle warning(s) |
| Missing evidence | 0 item(s) |
| Bundle warnings | 0 warning(s) |

## Decision-Support Boundary

ORBITAL provides decision support only: not approval, not authorization, not legal advice, not LAANC, and not operational clearance. The pilot-in-command and operator retain final responsibility for release.

## 10-Second Mission Read

| Signal | Current value | Operator cue |
| --- | --- | --- |
| Verdict | REVIEW REQUIRED | Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision. |
| Modeled mission status | GO | Use as the first feasibility read from the constraint audit. |
| Mission risk | LOW | Treat higher risk as a cue for additional operator review. |
| Top limiting constraint | Wind / weather margin, PASS, margin 3.1 m/s | Review this constraint before changing or releasing the mission. |
| Regulatory readiness | OPERATOR_ACTION_REQUIRED | Confirm required approvals, waivers, roles, and restrictions outside ORBITAL. |
| Evidence completeness | 100.0 % (17 / 17 artifacts present) | Confirm expected artifacts are present before sharing. |
| Regulatory documentation completeness | 100.0 % (8 / 8 fields documented) | Confirm optional evidence fields are documented where needed. |
| Weather fallback | FALLBACK USED: source offline Open-Meteo-shaped sample, timestamp 2026-09-11T16:00:00Z, reason weather.use_live is false; using offline sample | Refresh current field weather and keep the source with the bundle. |
| Uncertainty / robustness | PASS: 20 case(s), hard pass rate 100.0 %, worst hard margin 0.139 | Review robustness assumptions and rerun with scenario-specific uncertainty ranges if margins are close. |
| Evidence warnings | CLEAR: 0 missing artifact(s), 0 stale artifact(s), 0 missing evidence item(s), 0 bundle warning(s) | Check stale, missing, or mismatched evidence before archiving. |

## Trust And Defensibility

### Sample Data / Demo Scenario Note

Sample data / demo scenario: this bundle uses demonstration planning inputs, including offline or sample weather where configured. Replace route, weather, regulatory, crew, and customer evidence before operational use.

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
| Status | CLEAR |
| Missing artifacts | 0 |
| Stale artifacts | 0 |
| Missing evidence items | 0 |
| Bundle warnings | 0 |

Open `evidence_bundle_summary.md`, `manifest.json`, and `checksum_manifest.json` when any warning count is nonzero.

## Recommended Opening Sequence

1. Start here with the dashboard.
2. Open the primary constraint audit for feasibility and top-limiter rationale.
3. Open the what-if plan to see how mission changes affect feasibility.
4. Open regulatory readiness to confirm documentation-only action items.
5. Open the manifest, artifact index, and checksum manifest before archiving.

## Mission Snapshot

- Mission: BVLOS Powerline Inspection Demo
- Mission verdict: REVIEW REQUIRED
- Mission status: GO
- Mission risk: LOW
- Top limiting constraint: Wind / weather margin, PASS, margin 3.1 m/s
- Regulatory readiness: OPERATOR_ACTION_REQUIRED
- Bundle completeness: 100.0 % (17 / 17 artifacts present)
- Regulatory documentation completeness: 100.0 % (8 / 8 fields documented)
- Missing evidence items: 0
- Bundle warnings: 0

## Operator Review

Review status: ready for review
Reviewer name: not provided
Review timestamp UTC: not provided
Operator decision: pending operator review
Review notes: Demo bundle ready for operator review; final approval remains outside ORBITAL.

| Field | Value |
| --- | --- |
| Review status | ready for review |
| Reviewer name | not provided |
| Review timestamp UTC | not provided |
| Operator decision | pending operator review |
| Review notes | Demo bundle ready for operator review; final approval remains outside ORBITAL. |

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

- none

## Bundle Warnings

- none

## Next Operator Actions

- Complete the listed review items, confirm regulatory readiness outside ORBITAL, then record the operator decision.
- Review the primary constraint audit and top limiting constraint.
- Review the what-if plan if any constraint margin is tight.
- Verify bundle completeness, manifest, and checksum manifest before archiving.
- Record reviewer, timestamp, notes, and operator decision in scenario metadata when appropriate.
