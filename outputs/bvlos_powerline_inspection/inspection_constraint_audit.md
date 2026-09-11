# Drone Inspection Constraint Audit

Mission: BVLOS Powerline Inspection Demo
Status: GO
Mission risk: LOW

## Top Limiting Constraint

- Wind / weather margin: PASS with margin 3.1 m/s

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

- Status: PASS
- Margin: 132.1 Wh
- Warning margin: 70.0 Wh
- Observed: `{"final_battery_Wh": 832.0599780312521, "required_reserve_Wh": 700.0}`
- Recommended action: Reduce route length or plan a relaunch / battery swap.

### Wind / weather margin

- Status: PASS
- Margin: 3.1 m/s
- Warning margin: 2.0 m/s
- Observed: `{"max_horizontal_wind_mps": 5.9, "max_safe_wind_mps": 9.0, "precipitation_mm": 0.0, "temperature_C": 18.5, "visibility_m": 16000.0, "weather_audit_wind_mps": 5.9, "weather_fallback_used": true, "weather_source": "offline Open-Meteo-shaped sample", "weather_timestamp_utc": "2026-09-11T16:00:00Z", "weather_wind_direction_deg": 285.0, "weather_wind_gust_mps": 5.9, "weather_wind_speed_mps": 4.5}`
- Recommended action: Wait for better wind or lower mission scope.

### Geofence / no-fly-zone clearance

- Status: PASS
- Margin: 276.7 m
- Warning margin: 25.0 m
- Observed: `{"geofence_violated": false, "min_clearance_m": 351.69524979477507, "required_clearance_m": 75.0}`
- Recommended action: Adjust route geometry or increase no-fly-zone clearance.

### Route completion status

- Status: PASS
- Margin: 1.0 completion
- Warning margin: 0.5 completion
- Observed: `{"reached_all": true, "waypoints_completed": 6.0, "waypoints_total": 6.0}`
- Recommended action: Split the inspection into shorter sorties.

### Turn / bank feasibility

- Status: PASS
- Margin: 0.139 rad/s
- Warning margin: 0.05 rad/s
- Observed: `{"bank_max_deg": 30.0}`
- Recommended action: Lower cruise speed or add more turn spacing.
