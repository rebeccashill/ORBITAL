# BVLOS Inspection Operator Memo

Status: MODIFY / DO NOT FLY

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, or regulatory approval system.

## Mission Summary

- Mission: BVLOS Modify No-Go Fixture
- Inspection points: 6
- Planned cruise speed: 12.0 m/s
- Estimated flight time: 260.0 s
- Estimated energy used: 11.0 Wh
- Final battery: 839.0 Wh
- Objective score: 4208831.7

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

- REVIEW: battery_reserve (margin -41.0)
- PASS: turn_limit (margin 0.252)
- PASS: geofence_no_entry (margin 0.5)
- PASS: inspection_completion (margin 1.0)
- PASS: geofence_clearance (margin 273.1)

## Recommended Next Actions

- Reduce route length or plan a relaunch / battery swap.
- Wait for better wind before retrying if winds are the binding constraint.
