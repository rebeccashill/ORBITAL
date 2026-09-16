# BVLOS Inspection Operator Memo

Status: GO

ORBITAL is preflight decision support and audit evidence. It is not a LAANC provider, autopilot, or regulatory approval system.

## Mission Summary

- Mission: BVLOS Stale Evidence Fixture
- Inspection points: 6
- Planned cruise speed: 19.0 m/s
- Estimated flight time: 185.0 s
- Estimated energy used: 13.8 Wh
- Final battery: 836.2 Wh
- Objective score: 189.8

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

- Source: offline Open-Meteo-shaped sample
- Timestamp: 2026-09-11T16:00:00Z
- Wind speed: 4.5 m/s
- Wind gust: 5.9 m/s
- Visibility: 16000.0 m
- Precipitation: 0.0 mm
- Fallback used: yes

## Regulatory Metadata

- LAANC required: yes
- Waiver / authorization required: yes
- Airspace class: Class D
- Visual observer required: yes
- Ground-risk / population note: Utility corridor inspection over mixed industrial and lightly populated roadside areas; operator should review site-specific ground risk before dispatch.
- Documentation-only notice: For planning documentation only. ORBITAL does not provide LAANC, waivers, authorizations, legal approval, or operational clearance.

## Top Constraints

- PASS: turn_limit (margin 0.201)
- PASS: geofence_no_entry (margin 0.5)
- PASS: inspection_completion (margin 1.0)
- PASS: battery_reserve (margin 136.2)
- PASS: geofence_clearance (margin 272.7)

## Robustness

- Cases: 1
- Hard pass rate: 1.0
- Worst hard margin across cases: 0.201

## Recommended Next Actions

- Proceed if the pilot-in-command confirms airspace authorization, crew readiness, and field conditions.
- Wait for better wind if observed conditions exceed the scenario model.
- Maintain the modeled geofence clearance before export to any flight system.
