# Drone Inspection Constraint Audit

Mission: BVLOS Powerline Inspection Demo
Status: GO
Mission risk: LOW

## Top Limiting Constraint

- Wind / weather margin: PASS with margin 3.5 m/s

## Top Three Risk Drivers

- Wind / weather margin: PASS, margin 3.5 m/s, risk points 12.5
- Battery reserve margin: PASS, margin 131.9 Wh, risk points 11.2
- Route completion status: PASS, margin 1.0 completion, risk points 10.0

## Full Constraint Audit

### Battery reserve margin

- Status: PASS
- Margin: 131.9 Wh
- Warning margin: 70.0 Wh
- Observed: `{"final_battery_Wh": 831.8553549273508, "required_reserve_Wh": 700.0}`
- Recommended action: Reduce route length or plan a relaunch / battery swap.

### Wind / weather margin

- Status: PASS
- Margin: 3.5 m/s
- Warning margin: 2.0 m/s
- Observed: `{"max_horizontal_wind_mps": 5.5, "max_safe_wind_mps": 9.0}`
- Recommended action: Wait for better wind or lower mission scope.

### Geofence / no-fly-zone clearance

- Status: PASS
- Margin: 261.6 m
- Warning margin: 25.0 m
- Observed: `{"geofence_violated": false, "min_clearance_m": 336.6023274099015, "required_clearance_m": 75.0}`
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
