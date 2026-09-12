# Drone Inspection Constraint Audit

Primary demo artifact: this report is the operator-facing feasibility case for the modeled BVLOS inspection mission.

Core question: Can we safely and defensibly fly this mission?

Mission: BVLOS Powerline Inspection Demo
Status: GO
Mission risk: LOW

## Status Legend

- PASS: Modeled margin is outside the warning band.
- WARNING: Modeled margin is positive but close enough to require operator review.
- FAIL: Modeled margin is negative; modify the mission before release.
- UNKNOWN: ORBITAL does not have enough data to classify this group.

## Top Limiting Constraint

- Wind / weather margin: PASS with margin 3.1 m/s

## Constraint Group Summary

| Group | Status | Margin | Why this matters | Recommended operator action |
| --- | --- | ---: | --- | --- |
| Energy / battery reserve | PASS | 132.1 Wh | A BVLOS inspection needs enough remaining energy for delay, diversion, recovery, and conservative abort decisions. | Keep the reserve assumption, confirm launch battery state, and brief abort reserve before dispatch. |
| Weather / wind margin | PASS | 3.1 m/s | Wind reduces endurance, increases tracking error, and can turn a feasible route into a recovery or containment problem. | Confirm launch-time weather against operator minimums and keep the forecast source with the mission package. |
| Geofence / no-fly-zone clearance | PASS | 276.7 m | Geofence clearance protects people, assets, restricted areas, and customer boundaries when navigation or wind uncertainty appears. | Keep the geofence file and route review in the evidence bundle, then confirm site boundaries before flight. |
| Route completion | PASS | 1.0 completion | Incomplete route coverage can waste a crew deployment and create pressure to improvise in the field. | Confirm the waypoint list matches the inspection scope and brief any acceptable skipped-point policy. |
| Turn / bank feasibility | PASS | 0.139 rad/s | Overly aggressive turns can break route tracking, increase energy use, and reduce safety margins near assets or geofences. | Keep the planned speed and turn assumptions, then verify they match the aircraft operating envelope. |

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

## Regulatory Metadata

- LAANC required: yes
- Waiver / authorization required: yes
- Airspace class: Class D
- Visual observer required: yes
- Ground-risk / population note: Utility corridor inspection over mixed industrial and lightly populated roadside areas; operator should review site-specific ground risk before dispatch.
- Documentation-only notice: For planning documentation only. ORBITAL does not provide LAANC, waivers, authorizations, legal approval, or operational clearance.

## Weather Metadata

- Source: offline Open-Meteo-shaped sample
- Provider: open_meteo
- Timestamp: 2026-09-11T16:00:00Z
- Location: Palo Alto utility corridor demo
- Forecast window start: 2026-09-11T16:00:00Z
- Forecast window hours: 2.0
- Wind speed: 4.5 m/s
- Wind direction: 285.0 deg
- Wind gust: 5.9 m/s
- Visibility: 16000.0 m
- Precipitation: 0.0 mm
- Temperature: 18.5 C
- Fallback used: yes

## Top Three Risk Drivers

- Wind / weather margin: PASS, margin 3.1 m/s, risk points 14.5
- Battery reserve margin: PASS, margin 132.1 Wh, risk points 11.1
- Route completion status: PASS, margin 1.0 completion, risk points 10.0

## Full Constraint Audit

### Battery reserve margin

- Group: Energy / battery reserve
- What this checks: Checks whether the planned sortie lands with the operator-required battery reserve still available.
- Why this matters to an operator: A BVLOS inspection needs enough remaining energy for delay, diversion, recovery, and conservative abort decisions.
- Status: PASS
- Status meaning: Modeled margin is outside the warning band.
- Margin: 132.1 Wh
- Warning margin: 70.0 Wh
- Observed: `{"final_battery_Wh": 832.0599780312521, "required_reserve_Wh": 700.0}`
- Recommended operator action: Keep the reserve assumption, confirm launch battery state, and brief abort reserve before dispatch.

### Wind / weather margin

- Group: Weather / wind margin
- What this checks: Checks whether modeled or forecast wind stays below the configured safe operating limit.
- Why this matters to an operator: Wind reduces endurance, increases tracking error, and can turn a feasible route into a recovery or containment problem.
- Status: PASS
- Status meaning: Modeled margin is outside the warning band.
- Margin: 3.1 m/s
- Warning margin: 2.0 m/s
- Observed: `{"max_horizontal_wind_mps": 5.9, "max_safe_wind_mps": 9.0, "precipitation_mm": 0.0, "temperature_C": 18.5, "visibility_m": 16000.0, "weather_audit_wind_mps": 5.9, "weather_fallback_used": true, "weather_source": "offline Open-Meteo-shaped sample", "weather_timestamp_utc": "2026-09-11T16:00:00Z", "weather_wind_direction_deg": 285.0, "weather_wind_gust_mps": 5.9, "weather_wind_speed_mps": 4.5}`
- Recommended operator action: Confirm launch-time weather against operator minimums and keep the forecast source with the mission package.

### Geofence / no-fly-zone clearance

- Group: Geofence / no-fly-zone clearance
- What this checks: Checks whether the route remains outside no-fly zones and preserves the configured stand-off buffer.
- Why this matters to an operator: Geofence clearance protects people, assets, restricted areas, and customer boundaries when navigation or wind uncertainty appears.
- Status: PASS
- Status meaning: Modeled margin is outside the warning band.
- Margin: 276.7 m
- Warning margin: 25.0 m
- Observed: `{"geofence_violated": false, "min_clearance_m": 351.69524979477507, "required_clearance_m": 75.0}`
- Recommended operator action: Keep the geofence file and route review in the evidence bundle, then confirm site boundaries before flight.

### Route completion status

- Group: Route completion
- What this checks: Checks whether the candidate plan reaches all required inspection points.
- Why this matters to an operator: Incomplete route coverage can waste a crew deployment and create pressure to improvise in the field.
- Status: PASS
- Status meaning: Modeled margin is outside the warning band.
- Margin: 1.0 completion
- Warning margin: 0.5 completion
- Observed: `{"reached_all": true, "waypoints_completed": 6.0, "waypoints_total": 6.0}`
- Recommended operator action: Confirm the waypoint list matches the inspection scope and brief any acceptable skipped-point policy.

### Turn / bank feasibility

- Group: Turn / bank feasibility
- What this checks: Checks whether planned turns stay within configured bank-angle and turn-rate capability.
- Why this matters to an operator: Overly aggressive turns can break route tracking, increase energy use, and reduce safety margins near assets or geofences.
- Status: PASS
- Status meaning: Modeled margin is outside the warning band.
- Margin: 0.139 rad/s
- Warning margin: 0.05 rad/s
- Observed: `{"bank_max_deg": 30.0}`
- Recommended operator action: Keep the planned speed and turn assumptions, then verify they match the aircraft operating envelope.
