# ORBITAL Scenario Authoring Guide

This guide explains how to write YAML scenario files for ORBITAL aircraft and spacecraft missions.

Before running a new scenario, validate it:

```bash
python -m mission_framework.cli validate path/to/scenario.yaml
```

If ORBITAL is installed as a package, the console script works too:

```bash
orbital validate path/to/scenario.yaml
```

The validator reports all detected issues at once when possible, so you can fix the file in one pass.

## File Shape

Every scenario is a YAML mapping with shared top-level sections plus domain-specific sections.

Shared sections:

```yaml
scenario:
  name: "Human-readable scenario name"
  type: "aircraft" # or "spacecraft"

planner:
  iterations: 100
  restarts: 1

robustness:
  cases: 0

output:
  save_history: false
  verbose: true
```

Required shared fields:

| Field | Type | Expected range or value |
| --- | --- | --- |
| `scenario.name` | string | Non-empty |
| `scenario.type` | string | `aircraft` or `spacecraft` |
| `planner.iterations` | integer | `>= 1` |
| `planner.restarts` | integer | `>= 1` |
| `planner.penalty_weight` | number | Optional, `>= 0` |
| `planner.hard_infeasible_penalty` | number | Optional, `>= 0` |
| `planner.seed` | integer | Optional |
| `planner.history_stride` | integer | Optional, `>= 1` |
| `planner.stop_if_feasible_for` | integer | Optional, `>= 0` |
| `robustness.cases` | integer | `>= 0` |
| `robustness.aggregation` | string | Optional: `mean`, `worst`, or `cvar` |
| `robustness.cvar_alpha` | number | Optional, `0` to `1` |
| `robustness.report_percentiles` | list[number] | Optional, each value from `0` to `100` |
| `output.*` | boolean | Use `true` or `false` |

Planner mutation options are optional:

```yaml
planner:
  iterations: 200
  restarts: 2
  penalty_weight: 2000.0
  hard_infeasible_penalty: 1000000.0
  seed: 42
  mutation:
    cont_sigma: 0.15
    int_step: 1
    p_flip: 0.05
    p_perm_swap: 0.5
    perm_swaps: 2
```

Mutation ranges:

| Field | Type | Expected range |
| --- | --- | --- |
| `planner.mutation.cont_sigma` | number | `>= 0` |
| `planner.mutation.int_step` | integer | `>= 0` |
| `planner.mutation.p_flip` | number | `0` to `1` |
| `planner.mutation.p_perm_swap` | number | `0` to `1` |
| `planner.mutation.perm_swaps` | integer | `>= 0` |

## Aircraft YAML Structure

Aircraft scenarios describe an initial state, required waypoints, vehicle parameters, optional wind, optional geofences, constraints, objective terms, planner settings, robustness settings, and output settings.

Required aircraft sections:

```yaml
scenario:
initial_state:
mission:
vehicle:
constraints:
objective:
planner:
robustness:
output:
```

Common optional aircraft sections:

```yaml
wind:
geofence:
simulation:
```

### Aircraft Fields

| Field | Type | Expected range or value |
| --- | --- | --- |
| `initial_state.x_m` | number | meters |
| `initial_state.y_m` | number | meters |
| `initial_state.z_m` | number | Optional, meters |
| `initial_state.heading_rad` | number | radians |
| `initial_state.speed_mps` | number | `>= 0`, meters per second |
| `initial_state.battery_Wh` | number | `>= 0`, watt-hours |
| `mission.waypoints[].id` | string | Unique, non-empty |
| `mission.waypoints[].x_m` | number | meters |
| `mission.waypoints[].y_m` | number | meters |
| `mission.waypoints[].z_m` | number | Optional, meters |
| `mission.waypoints[].radius_m` | number | Optional, `>= 0`, meters |
| `vehicle.dt_s` | number | `>= 0`, seconds |
| `vehicle.reach_radius_m` | number | `>= 0`, meters |
| `vehicle.mass_kg` | number | `>= 0`, kilograms |
| `vehicle.min_speed_mps` | number | `>= 0` |
| `vehicle.cruise_speed_mps` | number | Between min and max speed |
| `vehicle.max_speed_mps` | number | `>= min_speed_mps` |
| `vehicle.battery_capacity_Wh` | number | `>= 0` |
| `vehicle.bank_max_deg` | number | Optional, `>= 0`, degrees |
| `vehicle.climb_rate_max_mps` | number | Optional, `>= 0` |
| `vehicle.descent_rate_max_mps` | number | Optional, `>= 0` |
| `geofence.no_fly_zones[].id` | string | Unique, non-empty |
| `geofence.no_fly_zones[].polygon` | list | At least 3 coordinate pairs |

Supported aircraft wind types:

```text
none, no_wind, zero, uniform, constant, sinusoidal, vortex, swirl
```

Supported aircraft objective terms:

```text
total_time, time, t_end_s, energy_used, energy, energy_used_wh
```

All `constraints.*` values must be booleans:

```yaml
constraints:
  enforce_waypoint_visit: true
  enforce_geofence: true
  enforce_energy_nonnegative: true
  enforce_turn_rate_limit: true
  enforce_speed_limits: true
```

### Minimal Aircraft Example

```yaml
scenario:
  name: "Minimal Aircraft Scenario"
  type: "aircraft"

initial_state:
  x_m: 0.0
  y_m: 0.0
  heading_rad: 0.0
  speed_mps: 20.0
  battery_Wh: 500.0

mission:
  waypoints:
    - id: "WP1"
      x_m: 1000.0
      y_m: 0.0
    - id: "WP2"
      x_m: 1500.0
      y_m: 800.0

vehicle:
  dt_s: 5.0
  reach_radius_m: 75.0
  mass_kg: 12.0
  min_speed_mps: 12.0
  cruise_speed_mps: 20.0
  max_speed_mps: 30.0
  battery_capacity_Wh: 500.0

constraints:
  enforce_waypoint_visit: true
  enforce_geofence: false
  enforce_energy_nonnegative: true
  enforce_turn_rate_limit: true
  enforce_speed_limits: true

objective:
  type: "weighted_sum"
  terms:
    - name: "total_time"
      weight: 1.0
      mode: "minimize"
    - name: "energy_used"
      weight: 0.2
      mode: "minimize"

planner:
  iterations: 100
  restarts: 1
  penalty_weight: 2000.0
  hard_infeasible_penalty: 1000000.0
  seed: 42
  mutation:
    cont_sigma: 0.15
    int_step: 1
    p_flip: 0.05
    p_perm_swap: 0.5
    perm_swaps: 2

robustness:
  cases: 0
  report_percentiles: [50, 90]

output:
  save_history: false
  export_flight_path: true
  export_constraint_report: true
  export_summary_metrics: true
  verbose: true
```

## Spacecraft YAML Structure

Spacecraft scenarios describe an orbit, science targets, ground stations, spacecraft resource limits, constraints, objective terms, planner settings, robustness settings, and output settings.

Required spacecraft sections:

```yaml
scenario:
orbit:
mission:
ground_stations:
spacecraft:
constraints:
objective:
planner:
robustness:
output:
```

Common optional spacecraft sections:

```yaml
downlink:
power:
ops:
```

### Spacecraft Fields

| Field | Type | Expected range or value |
| --- | --- | --- |
| `orbit.altitude_km` | number | `> 0`, kilometers |
| `orbit.inclination_deg` | number | `0` to `180`, degrees |
| `orbit.raan_deg` | number | Optional, degrees |
| `orbit.true_anomaly_deg` | number | Optional, degrees |
| `orbit.epoch_utc` | string | ISO-8601 datetime, for example `2026-01-01T00:00:00Z` |
| `orbit.duration_days` | number | `> 0` |
| `orbit.time_step_s` | number | `> 0`, seconds |
| `mission.targets[].id` | string | Unique, non-empty |
| `mission.targets[].lat_deg` | number | `-90` to `90` |
| `mission.targets[].lon_deg` | number | `-180` to `180` |
| `mission.targets[].value` | number | `>= 0` |
| `mission.targets[].obs_duration_s` | number | Optional, `> 0`, seconds |
| `mission.targets[].cooldown_s` | number | Optional, `>= 0`, seconds |
| `mission.targets[].time_windows[].start_utc` | string | ISO-8601 datetime |
| `mission.targets[].time_windows[].end_utc` | string | Later than `start_utc` |
| `ground_stations[].id` | string | Unique, non-empty |
| `ground_stations[].lat_deg` | number | `-90` to `90` |
| `ground_stations[].lon_deg` | number | `-180` to `180` |
| `ground_stations[].alt_km` | number | Optional, kilometers |
| `ground_stations[].min_elevation_deg` | number | `0` to `90`, degrees |
| `spacecraft.battery_capacity_Wh` | number | `> 0` |
| `spacecraft.initial_battery_Wh` | number | `0` to battery capacity |
| `spacecraft.charge_rate_W` | number | `>= 0` |
| `spacecraft.base_load_W` | number | `>= 0` |
| `spacecraft.payload_power_W` | number | `>= 0` |
| `spacecraft.downlink_power_W` | number | `>= 0` |
| `spacecraft.max_slew_rate_deg_per_s` | number | `> 0` |
| `spacecraft.min_cooldown_s` | number | `>= 0` |
| `spacecraft.max_ops_per_orbit` | integer | `>= 1` |
| `spacecraft.data_storage_capacity_Gb` | number | `> 0` |
| `spacecraft.data_rate_downlink_Mbps` | number | `> 0` |
| `spacecraft.data_rate_observation_Mbps` | number | `> 0` |
| `downlink.duration_s` | number | Optional, `> 0` |
| `downlink.max_windows_per_station` | integer | Optional, `>= 1` |
| `power.min_Wh` | number | Optional, `>= 0` |
| `ops.orbit_period_s` | number | Optional, `> 0` |

Supported spacecraft objective terms:

```text
science_value_delivered, value, mission_value, missed_downlink_penalty, power_violation_penalty
```

All `constraints.*` values must be booleans:

```yaml
constraints:
  enforce_visibility: true
  enforce_slew_limits: true
  enforce_power_nonnegative: true
  enforce_data_storage_limit: true
  enforce_cooldown: true
  enforce_max_ops_per_orbit: true
```

### Minimal Spacecraft Example

```yaml
scenario:
  name: "Minimal Spacecraft Scenario"
  type: "spacecraft"

orbit:
  altitude_km: 550.0
  inclination_deg: 97.6
  raan_deg: 0.0
  true_anomaly_deg: 0.0
  epoch_utc: "2026-01-01T00:00:00Z"
  duration_days: 1
  time_step_s: 60.0

mission:
  targets:
    - id: "TGT1"
      lat_deg: 34.05
      lon_deg: -118.25
      value: 10.0
      time_windows:
        - start_utc: "2026-01-01T00:00:00Z"
          end_utc: "2026-01-01T23:59:59Z"

ground_stations:
  - id: "GS1"
    lat_deg: 37.7749
    lon_deg: -122.4194
    min_elevation_deg: 10.0

spacecraft:
  battery_capacity_Wh: 120.0
  initial_battery_Wh: 100.0
  charge_rate_W: 35.0
  base_load_W: 20.0
  payload_power_W: 40.0
  downlink_power_W: 30.0
  max_slew_rate_deg_per_s: 1.0
  min_cooldown_s: 120.0
  max_ops_per_orbit: 4
  data_storage_capacity_Gb: 32.0
  data_rate_downlink_Mbps: 50.0
  data_rate_observation_Mbps: 25.0

constraints:
  enforce_visibility: true
  enforce_slew_limits: true
  enforce_power_nonnegative: true
  enforce_data_storage_limit: true
  enforce_cooldown: true
  enforce_max_ops_per_orbit: true

objective:
  type: "weighted_sum"
  terms:
    - name: "science_value_delivered"
      weight: 1.0
      mode: "maximize"

planner:
  iterations: 100
  restarts: 1
  penalty_weight: 3000.0
  hard_infeasible_penalty: 1000000.0
  seed: 123
  mutation:
    cont_sigma: 0.10
    int_step: 1
    p_flip: 0.05
    p_perm_swap: 0.4
    perm_swaps: 2

robustness:
  cases: 0
  report_percentiles: [50, 90]

output:
  export_schedule: true
  export_constraint_report: true
  export_summary_metrics: true
  save_history: true
  verbose: true
```

## Troubleshooting Validation Errors

### `scenario.type: unknown scenario type`

Use exactly one of:

```yaml
scenario:
  type: "aircraft"
```

or:

```yaml
scenario:
  type: "spacecraft"
```

### `required section is missing`

The scenario is missing a top-level section. Compare the file against the required section list for its domain.

### `required numeric field is missing`

A required number is absent. For example, aircraft waypoints need both `x_m` and `y_m`; spacecraft targets need `lat_deg`, `lon_deg`, and `value`.

### `must be a finite number`

The value must be a YAML number, not a quoted word, boolean, empty field, `nan`, or `inf`.

Good:

```yaml
speed_mps: 20.0
```

Bad:

```yaml
speed_mps: "fast"
```

### `must be a boolean`

Use YAML booleans for constraint and output flags:

```yaml
enforce_geofence: true
```

Do not use strings:

```yaml
enforce_geofence: "yes"
```

### `must fall between vehicle.min_speed_mps and vehicle.max_speed_mps`

For aircraft, the cruise speed must be inside the allowed speed range:

```yaml
vehicle:
  min_speed_mps: 12.0
  cruise_speed_mps: 20.0
  max_speed_mps: 30.0
```

### `coordinates must be finite numbers`

No-fly-zone polygons must use numeric `[x_m, y_m]` pairs:

```yaml
polygon:
  - [2500.0, 0.0]
  - [3000.0, 0.0]
  - [3000.0, 800.0]
```

### `end_utc: must be later than start_utc`

For spacecraft target windows, the end time must be after the start time:

```yaml
time_windows:
  - start_utc: "2026-01-01T00:00:00Z"
    end_utc: "2026-01-02T00:00:00Z"
```

### `initial_battery_Wh: must be less than or equal to spacecraft.battery_capacity_Wh`

For spacecraft, initial battery cannot exceed capacity:

```yaml
spacecraft:
  battery_capacity_Wh: 120.0
  initial_battery_Wh: 100.0
```

### `IDs must be unique within this list`

Waypoint IDs, target IDs, ground station IDs, and no-fly-zone IDs should not repeat within their own lists.

## Recommended Authoring Workflow

1. Copy the closest bundled example from `examples/`.
2. Change `scenario.name`.
3. Edit mission geometry or target lists.
4. Run `orbital validate path/to/scenario.yaml`.
5. Fix all validation errors.
6. Run a small smoke solve:

```bash
python -m mission_framework.cli path/to/scenario.yaml --iterations 20 --restarts 1 --robustness 0 --no-plots
```

7. Increase iterations, restarts, robustness cases, and plot generation once the scenario validates and runs.
