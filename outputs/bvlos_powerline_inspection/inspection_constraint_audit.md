# Drone Inspection Constraint Audit

Primary demo artifact: this report is the operator-facing feasibility case for the modeled BVLOS inspection mission.

Core question: Can we safely and defensibly fly this mission?

Mission: BVLOS Powerline Inspection Demo
Status: GO
Mission risk: LOW

## Operator Handoff

| Signal | Value | How to use it |
| --- | --- | --- |
| Mission status | GO | First feasibility read from the modeled constraints. |
| Mission risk | LOW | Higher risk means the operator should spend more time on the top drivers. |
| Top limiting constraint | Wind / weather margin, PASS, margin 3.1 m/s | Start the detailed review here before changing or releasing the mission. |

## Status Legend

- PASS: Modeled margin is above the configured review threshold.
- WARNING: Modeled margin is positive, but close enough to require operator review.
- FAIL: Modeled margin is negative; modify the mission before release.
- UNKNOWN: ORBITAL does not have enough data to classify this group.

## Top Limiting Constraint

- Constraint: Wind / weather margin
- Status: PASS
- Margin: 3.1 m/s
- Plain-English read: Wind / weather margin still passes, but it is the constraint group ORBITAL would review first because it has the highest modeled risk score.
- Why this matters: Wind reduces endurance, increases tracking error, and can turn a feasible route into a recovery or containment problem.
- Operator action: Confirm launch-time weather against operator minimums and keep the forecast source with the mission package.
- Selection detail: Wind / weather margin was selected because it had the highest risk_points value (14.5) among 5 audited constraint groups. Its margin was 3.1 m/s against a warning threshold of 2.0 m/s.
- Selection method: risk_points_descending

## Plain-English Constraint Guide

| Constraint group | Plain-English read | Operator action |
| --- | --- | --- |
| Energy / battery reserve | Checks whether the planned sortie lands with the operator-required battery reserve still available. | Keep the reserve assumption, confirm launch battery state, and brief abort reserve before dispatch. |
| Weather / wind margin | Checks whether modeled or forecast wind stays below the configured safe operating limit. | Confirm launch-time weather against operator minimums and keep the forecast source with the mission package. |
| Geofence / no-fly-zone clearance | Checks whether the route remains outside no-fly zones and preserves the configured stand-off buffer. | Keep the geofence file and route review in the evidence bundle, then confirm site boundaries before flight. |
| Route completion | Checks whether the candidate plan reaches all required inspection points. | Confirm the waypoint list matches the inspection scope and brief any acceptable skipped-point policy. |
| Turn / bank feasibility | Checks whether planned turns stay within configured bank-angle and turn-rate capability. | Keep the planned speed and turn assumptions, then verify they match the aircraft operating envelope. |

## Constraint Group Summary

| Group | Status | Margin | What ORBITAL checked | Why this matters | Recommended operator action |
| --- | --- | ---: | --- | --- | --- |
| Energy / battery reserve | PASS | 132.1 Wh | Checks whether the planned sortie lands with the operator-required battery reserve still available. | A BVLOS inspection needs enough remaining energy for delay, diversion, recovery, and conservative abort decisions. | Keep the reserve assumption, confirm launch battery state, and brief abort reserve before dispatch. |
| Weather / wind margin | PASS | 3.1 m/s | Checks whether modeled or forecast wind stays below the configured safe operating limit. | Wind reduces endurance, increases tracking error, and can turn a feasible route into a recovery or containment problem. | Confirm launch-time weather against operator minimums and keep the forecast source with the mission package. |
| Geofence / no-fly-zone clearance | PASS | 276.7 m | Checks whether the route remains outside no-fly zones and preserves the configured stand-off buffer. | Geofence clearance protects people, assets, restricted areas, and customer boundaries when navigation or wind uncertainty appears. | Keep the geofence file and route review in the evidence bundle, then confirm site boundaries before flight. |
| Route completion | PASS | 1.0 completion | Checks whether the candidate plan reaches all required inspection points. | Incomplete route coverage can waste a crew deployment and create pressure to improvise in the field. | Confirm the waypoint list matches the inspection scope and brief any acceptable skipped-point policy. |
| Turn / bank feasibility | PASS | 0.139 rad/s | Checks whether planned turns stay within configured bank-angle and turn-rate capability. | Overly aggressive turns can break route tracking, increase energy use, and reduce safety margins near assets or geofences. | Keep the planned speed and turn assumptions, then verify they match the aircraft operating envelope. |

## Model Transparency

### Assumptions Report

#### Battery / energy model

- Source: scenario.initial_state, scenario.vehicle, simulation scalars, and battery constraints
- Assumption: Battery feasibility is based on the configured capacity, initial charge, reserve policy, and simplified power model coefficients.
- Operator review note: Confirm aircraft battery health, payload draw, temperature effects, and abort reserve outside ORBITAL before release.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| initial battery | 850.0 | Wh | initial_state.battery_Wh |
| battery capacity | 900.0 | Wh | vehicle.battery_capacity_Wh |
| required battery reserve | 700.0 | Wh | vehicle.battery_reserve_Wh |
| final simulated battery | 832.0599780312521 | Wh | simulation.scalars.final_battery_Wh |
| energy used | 17.940021968747942 | Wh | simulation.scalars.energy_used_Wh |

#### Wind / weather model

- Source: scenario.wind, scenario.weather, weather.resolved, and simulation wind resources
- Assumption: Wind feasibility compares the modeled or weather-provided wind exposure against the configured safe operating limit.
- Operator review note: Refresh field weather and gust observations close to launch, especially when offline or sample weather is used.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| wind model type | sinusoidal |  | wind.type |
| maximum safe wind | 9.0 | m/s | wind.max_safe_wind_mps |
| weather wind gust | 5.9 | m/s | weather.resolved.wind_gust_mps |
| weather source | offline Open-Meteo-shaped sample |  | weather.resolved.source |
| weather timestamp | 2026-09-11T16:00:00Z | UTC | weather.resolved.timestamp_utc |

#### Geofence / no-fly-zone model

- Source: scenario.geofence, imported GeoJSON zones, and simulation geofence scalars
- Assumption: Geofence feasibility treats configured polygons and imported GeoJSON zones as the planning boundary source.
- Operator review note: Confirm site boundaries, customer buffers, and launch/recovery areas on current maps before export or dispatch.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| required clearance | 75.0 | m | geofence.clearance_m |
| manual no-fly zones | 1 | zones | geofence.no_fly_zones |
| GeoJSON geofence path | examples/geojson/bvlos_powerline_geofences.geojson |  | geofence.geojson_path |
| minimum simulated clearance | 351.69524979477507 | m | simulation.scalars.geofence_min_clearance_m |

#### Route completion model

- Source: scenario.mission, route GeoJSON, plan waypoints, and simulation completion scalars
- Assumption: The route is considered complete only when the simulation reaches the required inspection waypoints under the configured reach radius.
- Operator review note: Confirm the waypoint list matches the inspection scope and define any acceptable skipped-point policy before dispatch.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| route source | examples\geojson\bvlos_powerline_route.geojson |  | mission.route_geojson_path or mission.waypoints |
| fixed route order | True | boolean | mission.fixed_order |
| inspection waypoints | 6 | waypoints | mission.waypoints |
| waypoints completed | 6.0 | waypoints | simulation.scalars.waypoints_completed |
| route completion enforced | True | boolean | constraints.enforce_inspection_completion |

#### Turn / bank feasibility model

- Source: scenario.vehicle, simulated yaw-rate resources, and bank-angle constraint margins
- Assumption: Turn feasibility uses a simplified bank-angle/yaw-rate envelope rather than aircraft-specific autopilot tracking or detailed aerodynamics.
- Operator review note: Confirm the route geometry, turn spacing, and selected speed are within the aircraft operating envelope.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| bank limit | 30.0 | deg | vehicle.bank_max_deg |
| planned cruise speed | 27.407211792031063 | m/s | plan.metadata.cruise_speed_mps |
| minimum airspeed | 12.0 | m/s | vehicle.min_speed_mps |
| maximum airspeed | 28.0 | m/s | vehicle.max_speed_mps |

#### Robustness model

- Source: scenario.robustness and planner robustness summary
- Assumption: Robustness reflects configured Monte Carlo perturbations only; it is not a certification, reliability guarantee, or live safety monitor.
- Operator review note: Increase robustness cases or add scenario-specific uncertainty ranges when margin sensitivity matters.

| Input | Value | Unit | Source |
| --- | ---: | --- | --- |
| robustness cases configured | 20 | cases | robustness.cases |
| robustness cases run | 20 | cases | robustness summary |
| wind scale range | [0.8, 1.2] | multiplier | robustness.wind_scale_range |
| battery variation | 0.05 | fraction | robustness.battery_variation_pct |
| hard pass rate | 1.0 | ratio | robustness summary.hard_pass_rate |

### Constraint Margin Units And Sources

| Constraint | Unit | Margin source | Warning margin source |
| --- | --- | --- | --- |
| Battery reserve margin | Wh | constraint_result.battery_reserve.min_margin with fallback to simulation.scalars.final_battery_Wh - vehicle.battery_reserve_Wh | max(50 Wh, 10 percent of vehicle.battery_reserve_Wh) |
| Wind / weather margin | m/s | wind.max_safe_wind_mps minus the larger of simulation wind resources and weather.resolved wind speed or gust | wind.warning_margin_mps or default 2.0 m/s |
| Geofence / no-fly-zone clearance | m | constraint_result.geofence_clearance.min_margin with no-entry violation override from constraint_result.geofence_no_entry | max(25 m, 25 percent of geofence.clearance_m) |
| Route completion status | completion | simulation.metadata.reached_all and simulation.scalars waypoint counts | fixed 0.5 completion warning band |
| Turn / bank feasibility | rad/s | constraint_result.bank_angle_turn_limit.min_margin | vehicle.turn_warning_margin_radps or default 0.05 rad/s |

### Reproducibility

- Scenario path: C:\Users\shill\OneDrive\Desktop\ORBITAL\examples\bvlos_powerline_inspection_demo.yaml
- Seed: 7
- Iterations: 300
- Restarts: 1
- Robustness cases configured: 20
- Robustness cases run: 20
- Command: C:\Users\shill\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m mission_framework.cli examples/bvlos_powerline_inspection_demo.yaml --outdir outputs
- ORBITAL version: 1.0.10

### Model Limitations

- applies: Weather may come from offline, fallback, or sample inputs. ORBITAL records the source and timestamp, but the operator must verify current field weather before release.
- applies: Aircraft dynamics are simplified for feasibility planning. ORBITAL does not model every autopilot behavior, controller response, payload effect, battery aging factor, sensor constraint, or emergency maneuver.
- applies: Constraint margins are planning evidence for operator review. They do not approve a flight, issue authorization, or replace pilot-in-command judgment.

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

## Detailed Operator Review

### Battery reserve margin

- Group: Energy / battery reserve
- What this checks: Checks whether the planned sortie lands with the operator-required battery reserve still available.
- Why this matters to an operator: A BVLOS inspection needs enough remaining energy for delay, diversion, recovery, and conservative abort decisions.
- Status: PASS
- Status meaning: Modeled margin is above the configured review threshold.
- Margin: 132.1 Wh
- Warning margin: 70.0 Wh
- Observed evidence: final battery Wh: 832.1; required reserve Wh: 700.0
- Recommended operator action: Keep the reserve assumption, confirm launch battery state, and brief abort reserve before dispatch.

### Wind / weather margin

- Group: Weather / wind margin
- What this checks: Checks whether modeled or forecast wind stays below the configured safe operating limit.
- Why this matters to an operator: Wind reduces endurance, increases tracking error, and can turn a feasible route into a recovery or containment problem.
- Status: PASS
- Status meaning: Modeled margin is above the configured review threshold.
- Margin: 3.1 m/s
- Warning margin: 2.0 m/s
- Observed evidence: max horizontal wind mps: 5.9; weather audit wind mps: 5.9; max safe wind mps: 9.0; weather source: offline Open-Meteo-shaped sample; weather timestamp utc: 2026-09-11T16:00:00Z; 7 more fields in the JSON audit
- Recommended operator action: Confirm launch-time weather against operator minimums and keep the forecast source with the mission package.

### Geofence / no-fly-zone clearance

- Group: Geofence / no-fly-zone clearance
- What this checks: Checks whether the route remains outside no-fly zones and preserves the configured stand-off buffer.
- Why this matters to an operator: Geofence clearance protects people, assets, restricted areas, and customer boundaries when navigation or wind uncertainty appears.
- Status: PASS
- Status meaning: Modeled margin is above the configured review threshold.
- Margin: 276.7 m
- Warning margin: 25.0 m
- Observed evidence: required clearance m: 75.0; min clearance m: 351.7; geofence violated: no
- Recommended operator action: Keep the geofence file and route review in the evidence bundle, then confirm site boundaries before flight.

### Route completion status

- Group: Route completion
- What this checks: Checks whether the candidate plan reaches all required inspection points.
- Why this matters to an operator: Incomplete route coverage can waste a crew deployment and create pressure to improvise in the field.
- Status: PASS
- Status meaning: Modeled margin is above the configured review threshold.
- Margin: 1.0 completion
- Warning margin: 0.5 completion
- Observed evidence: waypoints completed: 6.0; waypoints total: 6.0; reached all: yes
- Recommended operator action: Confirm the waypoint list matches the inspection scope and brief any acceptable skipped-point policy.

### Turn / bank feasibility

- Group: Turn / bank feasibility
- What this checks: Checks whether planned turns stay within configured bank-angle and turn-rate capability.
- Why this matters to an operator: Overly aggressive turns can break route tracking, increase energy use, and reduce safety margins near assets or geofences.
- Status: PASS
- Status meaning: Modeled margin is above the configured review threshold.
- Margin: 0.139 rad/s
- Warning margin: 0.05 rad/s
- Observed evidence: bank max deg: 30.0
- Recommended operator action: Keep the planned speed and turn assumptions, then verify they match the aircraft operating envelope.
