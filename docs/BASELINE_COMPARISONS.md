# Baseline Comparison Reports

ORBITAL includes a reproducible baseline report so optimizer results can be
compared against simple reference planners instead of judged in isolation.

## Baseline Planners

- `random_search`: samples random feasible decision assignments and keeps the
  best nominal score.
- `greedy_routing`: aircraft-only nearest-neighbor waypoint routing from the
  initial position.
- `earliest_deadline`: spacecraft-only scheduling heuristic that selects all
  declared targets, starts observations at the earliest available visibility
  window, and uses the earliest downlink placement policy.

## Reproduce

```bash
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --out outputs/validation/baselines/baselines.csv --orbital-iterations 200 --orbital-restarts 1 --random-samples 50 --robustness-cases 5 --seed 0
```

The command writes:

- `outputs/validation/baselines/baselines.csv`
- `outputs/validation/baselines/baselines.md`
- `outputs/validation/baselines/README.txt`

## Current Results

Lower score is better. Robust hard pass rate is measured by reevaluating each
final assignment across five Monte Carlo cases.

| Domain | Planner | Score | Feasible | Runtime (s) | Robust hard pass rate |
| --- | --- | ---: | --- | ---: | ---: |
| aircraft | `orbital` | 311.846 | yes | 9.497 | 1.0 |
| aircraft | `random_search` | 321.716 | yes | 3.285 | 1.0 |
| aircraft | `greedy_routing` | 844.916 | no | 0.248 | 0.0 |
| spacecraft | `orbital` | -33.000 | yes | 52.680 | 1.0 |
| spacecraft | `random_search` | -33.000 | yes | 14.218 | 1.0 |
| spacecraft | `earliest_deadline` | -33.000 | yes | 1.520 | 1.0 |

## Interpretation

For the aircraft demo, ORBITAL finds a lower-cost feasible route than the
random baseline, while the nearest-neighbor route is rejected by the same hard
geofence constraint used by the planner. This makes the value of constraint-aware
search visible.

For the spacecraft demo, ORBITAL, random search, and earliest-deadline scheduling
all deliver the full 33-point science value. That is a useful result: it shows
the demo scenario is intentionally easy, and harder spacecraft scenarios should
be added when benchmarking future planner improvements.
