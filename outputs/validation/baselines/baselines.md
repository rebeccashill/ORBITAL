# Baseline Comparison Report

This report compares ORBITAL against simple reference planners using the same scenario builders, simulator, objective, constraints, and robustness evaluator.

Lower score is better. Feasibility means all hard constraints pass. Robust hard pass rate is measured by reevaluating the final assignment across the configured Monte Carlo cases.

## Baseline Planners

- `random_search`: sample random feasible decision assignments and keep the best nominal score.
- `greedy_routing`: aircraft nearest-neighbor route through required waypoints.
- `earliest_deadline`: spacecraft schedule observations and downlinks as early as the current decision model allows, prioritizing earliest declared deadlines.

## Reproduce

```bash
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --out outputs/validation/baselines/baselines.csv --orbital-iterations 200 --orbital-restarts 1 --random-samples 50 --robustness-cases 5 --seed 0
```

## Results

| Domain | Planner | Score | Feasible | Runtime (s) | Robust Cases | Hard Pass Rate | Worst Robust Margin |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| aircraft | `orbital` | 311.846 | yes | 9.49675 | 5 | 1 | 0.0925196 |
| aircraft | `random_search` | 321.716 | yes | 3.28549 | 5 | 1 | 0.0970243 |
| aircraft | `greedy_routing` | 844.916 | no | 0.247801 | 5 | 0 | -0.5 |
| spacecraft | `orbital` | -33 | yes | 52.6805 | 5 | 1 | 0 |
| spacecraft | `random_search` | -33 | yes | 14.2183 | 5 | 1 | 0 |
| spacecraft | `earliest_deadline` | -33 | yes | 1.51992 | 5 | 1 | 0 |

## Notes

- ORBITAL rows are solved nominally, then the final assignment is evaluated against the same robustness cases as the baselines.
- Runtime includes method execution plus final robustness evaluation.
- The CSV file contains additional objective, penalty, and worst hard constraint fields for auditability.
