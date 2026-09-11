# Optimizer Maturity Benchmark Report

This report broadens ORBITAL's optimizer evidence beyond the two demo scenarios. It runs demo and stress YAML files through the shared simulator, objective, constraints, and robustness evaluator, then compares ORBITAL against simple baselines and a small exhaustive_grid solver-style baseline.

The optimizer is strong demo and research engineering, but it is not yet production-grade mission planning. Treat these numbers as reproducible evidence for the checked-in models, not as validation against established flight or operations planning tools.

## Compared Planners

- `orbital`: shared stochastic local-search planner.
- `random_search`: random feasible decision assignments, best nominal score kept.
- `greedy_routing`: aircraft nearest-neighbor waypoint route.
- `earliest_deadline`: spacecraft observations ordered by declared deadlines.
- `exhaustive_grid`: enumerates the small discretized decision grid used by the checked-in scenarios. It is solver-style and auditable, but not a continuous global optimizer.

## Reproduce

```bash
python scripts/run_optimizer_maturity.py --scenario examples/aircraft_uav_demo.yaml --scenario examples/cubesat_leo_demo.yaml --scenario examples/stress/aircraft_high_wind.yaml --scenario examples/stress/aircraft_low_battery_tight_nfzs.yaml --scenario examples/stress/spacecraft_power_starved.yaml --scenario examples/stress/spacecraft_slew-constrained.yaml --out outputs/validation/optimizer_maturity/optimizer_maturity.csv --orbital-iterations 120 --orbital-restarts 1 --random-samples 25 --robustness-cases 3 --speed-grid 5 --offset-grid 3 --max-exhaustive-candidates 5000 --seed 0
```

## Best Planner By Scenario

| Group | Domain | Scenario | Best Planner | Score | Feasible | Robust Pass Rate |
| --- | --- | --- | --- | ---: | --- | ---: |
| demo | aircraft | UAV Multi-Waypoint Mission Demo | `orbital` | 311.886 | yes | 1 |
| demo | spacecraft | CubeSat 7-Day Earth Observation Demo | `orbital` | -33 | yes | 1 |
| stress | aircraft | UAV Stress - High Wind & Gusts | `orbital` | 311.972 | yes | 1 |
| stress | aircraft | UAV Stress - Low Battery & Tight Geofence | `orbital` | 906.127 | no | 0 |
| stress | spacecraft | CubeSat Stress - Power Starved | `random_search` | -33 | yes | 1 |
| stress | spacecraft | CubeSat Stress - Slew Constrained | `orbital` | -33 | yes | 1 |

## Full Results

| Group | Domain | Scenario | Planner | Category | Candidates | Score | Feasible | Runtime (s) | Robust Pass Rate | Worst Robust Margin |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| demo | aircraft | UAV Multi-Waypoint Mission Demo | `orbital` | optimizer | 120 | 311.886 | yes | 0.658244 | 1 | 0.092321 |
| demo | aircraft | UAV Multi-Waypoint Mission Demo | `random_search` | baseline | 25 | 321.716 | yes | 0.186741 | 1 | 0.0970243 |
| demo | aircraft | UAV Multi-Waypoint Mission Demo | `greedy_routing` | baseline | 1 | 844.916 | no | 0.0190669 | 0 | -0.5 |
| demo | aircraft | UAV Multi-Waypoint Mission Demo | `exhaustive_grid` | solver_style | 30 | 312.625 | yes | 0.235772 | 1 | 0.0887291 |
| demo | spacecraft | CubeSat 7-Day Earth Observation Demo | `orbital` | optimizer | 120 | -33 | yes | 3.26903 | 1 | 0 |
| demo | spacecraft | CubeSat 7-Day Earth Observation Demo | `random_search` | baseline | 25 | -33 | yes | 0.629988 | 1 | 0 |
| demo | spacecraft | CubeSat 7-Day Earth Observation Demo | `earliest_deadline` | baseline | 1 | -33 | yes | 0.0804697 | 1 | 0 |
| demo | spacecraft | CubeSat 7-Day Earth Observation Demo | `exhaustive_grid` | solver_style | 192 | -33 | yes | 4.32133 | 1 | 0 |
| stress | aircraft | UAV Stress - High Wind & Gusts | `orbital` | optimizer | 120 | 311.972 | yes | 0.467008 | 1 | 0.0918903 |
| stress | aircraft | UAV Stress - High Wind & Gusts | `random_search` | baseline | 25 | 401.144 | yes | 0.151329 | 1 | 0.16876 |
| stress | aircraft | UAV Stress - High Wind & Gusts | `greedy_routing` | baseline | 1 | 844.916 | no | 0.0135994 | 0 | -0.5 |
| stress | aircraft | UAV Stress - High Wind & Gusts | `exhaustive_grid` | solver_style | 30 | 312.625 | yes | 0.160174 | 1 | 0.0887291 |
| stress | aircraft | UAV Stress - Low Battery & Tight Geofence | `orbital` | optimizer | 120 | 906.127 | no | 0.578972 | 0 | -0.5 |
| stress | aircraft | UAV Stress - Low Battery & Tight Geofence | `random_search` | baseline | 25 | 982.715 | no | 0.171949 | 0 | -0.5 |
| stress | aircraft | UAV Stress - Low Battery & Tight Geofence | `greedy_routing` | baseline | 1 | 984.832 | no | 0.0187681 | 0 | -0.5 |
| stress | aircraft | UAV Stress - Low Battery & Tight Geofence | `exhaustive_grid` | solver_style | 30 | 937.787 | no | 0.205021 | 0 | -0.5 |
| stress | spacecraft | CubeSat Stress - Power Starved | `orbital` | optimizer | 120 | -23 | yes | 2.50197 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Power Starved | `random_search` | baseline | 25 | -33 | yes | 0.755911 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Power Starved | `earliest_deadline` | baseline | 1 | -33 | yes | 0.103175 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Power Starved | `exhaustive_grid` | solver_style | 192 | -33 | yes | 7.64523 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Slew Constrained | `orbital` | optimizer | 120 | -33 | yes | 2.73501 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Slew Constrained | `random_search` | baseline | 25 | -33 | yes | 0.654719 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Slew Constrained | `earliest_deadline` | baseline | 1 | -33 | yes | 0.0765285 | 1 | 0 |
| stress | spacecraft | CubeSat Stress - Slew Constrained | `exhaustive_grid` | solver_style | 192 | -33 | yes | 5.45379 | 1 | 0 |

## Maturity Readout

- This expands stress evidence by running the high-wind, tight-geofence, power-starved, and slew-constrained scenarios in one reproducible matrix.
- `exhaustive_grid` gives a stronger small-problem comparison than random or single-pass greedy heuristics where enumeration is practical.
- Matching or trailing `exhaustive_grid` on a checked-in scenario should be read as useful calibration, not failure: the grid has scenario-specific knowledge and can afford full enumeration at this small scale.
- The current spacecraft examples are still proxy-heavy and relatively easy. A production-grade claim would need comparisons against established orbital or mission-planning methods, clearer physical assumptions, richer benchmark scenarios, and at least one genuinely hard scheduling case.
