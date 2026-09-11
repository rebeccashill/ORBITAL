# BVLOS Inspection Operator Memo

Status: GO

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, or regulatory approval system.

## Mission Summary

- Mission: BVLOS Powerline Inspection Demo
- Inspection points: 6
- Planned cruise speed: 27.6 m/s
- Estimated flight time: 140.0 s
- Estimated energy used: 18.1 Wh
- Final battery: 831.9 Wh
- Objective score: 146.4

## Regulatory Metadata

- LAANC required: yes
- Waiver / authorization required: yes
- Airspace class: Class D
- Visual observer required: yes
- Ground-risk / population note: Utility corridor inspection over mixed industrial and lightly populated roadside areas; operator should review site-specific ground risk before dispatch.
- Documentation-only notice: For planning documentation only. ORBITAL does not provide LAANC, waivers, authorizations, legal approval, or operational clearance.

## Top Constraints

- PASS: turn_limit (margin 0.139)
- PASS: geofence_no_entry (margin 0.5)
- PASS: inspection_completion (margin 1.0)
- PASS: battery_reserve (margin 131.9)
- PASS: geofence_clearance (margin 261.6)

## Robustness

- Cases: 20
- Hard pass rate: 1.0
- Worst hard margin across cases: 0.139

## Recommended Next Actions

- Proceed if the pilot-in-command confirms airspace authorization, crew readiness, and field conditions.
- Wait for better wind if observed conditions exceed the scenario model.
- Maintain the modeled geofence clearance before export to any flight system.
