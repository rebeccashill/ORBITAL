# BVLOS Inspection Operator Memo

Status: GO

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, or regulatory approval system.

## Mission Summary

- Mission: BVLOS Ready Evidence Fixture
- Inspection points: 6
- Planned cruise speed: 22.4 m/s
- Estimated flight time: 165.0 s
- Estimated energy used: 15.6 Wh
- Final battery: 834.4 Wh
- Objective score: 170.5

## Mission / Fleet Metadata

- Operator: ORBITAL Demo Operations
- Aircraft ID: UAV-BVLOS-104
- Pilot: Demo Pilot
- Organization: Utility Inspection Team
- Asset owner: Palo Alto Grid Demo
- Drone model: Multirotor inspection UAV
- Battery pack ID: PACK-900WH-A
- Sensor payload: RGB + thermal inspection camera
- Inspection type: Powerline corridor inspection

## Weather

- Source: Operator-packaged field weather observation
- Timestamp: 2026-09-15T05:15:00Z
- Wind speed: 4.2 m/s
- Wind gust: 5.4 m/s
- Visibility: 18000.0 m
- Precipitation: 0.0 mm
- Fallback used: no

## Regulatory Metadata

- LAANC required: no
- Waiver / authorization required: no
- Airspace class: Class G fixture corridor
- Visual observer required: no
- Ground-risk / population note: Fixture corridor over controlled utility access roads; no public overflight modeled.
- Documentation-only notice: Fixture data for customer-discovery testing; ORBITAL does not provide approval or clearance.

## Top Constraints

- PASS: turn_limit (margin 0.166)
- PASS: geofence_no_entry (margin 0.5)
- PASS: inspection_completion (margin 1.0)
- PASS: battery_reserve (margin 134.4)
- PASS: geofence_clearance (margin 254.1)

## Robustness

- Cases: 1
- Hard pass rate: 1.0
- Worst hard margin across cases: 0.166

## Recommended Next Actions

- Proceed if the pilot-in-command confirms airspace authorization, crew readiness, and field conditions.
- Wait for better wind if observed conditions exceed the scenario model.
- Maintain the modeled geofence clearance before export to any flight system.
