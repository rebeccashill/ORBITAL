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
