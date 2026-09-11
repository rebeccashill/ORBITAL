# Optimizer Maturity

ORBITAL now includes a reproducible optimizer maturity benchmark in addition to
the simpler baseline comparison report.

## What It Adds

The maturity benchmark runs the shared planner on both demo scenarios and all
checked-in stress scenarios:

- `examples/aircraft_uav_demo.yaml`
- `examples/cubesat_leo_demo.yaml`
- `examples/stress/aircraft_high_wind.yaml`
- `examples/stress/aircraft_low_battery_tight_nfzs.yaml`
- `examples/stress/spacecraft_power_starved.yaml`
- `examples/stress/spacecraft_slew-constrained.yaml`

It compares ORBITAL with:

- `random_search`: random feasible assignments, best nominal score kept.
- `greedy_routing`: aircraft nearest-neighbor waypoint routing.
- `earliest_deadline`: spacecraft observations ordered by declared deadlines.
- `exhaustive_grid`: a small solver-style enumerator for discretized decisions.

`exhaustive_grid` is stronger than the simple heuristics where enumeration is
practical, but it is not a continuous global optimizer or a production mission
planning solver.

## Reproduce

```bash
python scripts/run_optimizer_maturity.py --out outputs/validation/optimizer_maturity/optimizer_maturity.csv --orbital-iterations 120 --orbital-restarts 1 --random-samples 25 --robustness-cases 3 --speed-grid 5 --offset-grid 3 --max-exhaustive-candidates 5000 --seed 0
```

The command writes:

- `outputs/validation/optimizer_maturity/optimizer_maturity.csv`
- `outputs/validation/optimizer_maturity/optimizer_maturity.md`
- `outputs/validation/optimizer_maturity/README.txt`

## Interpretation

The optimizer is strong demo and research engineering, but not yet
production-grade mission planning. Current evidence is enough to show the shared
planner can run across domains, handle constraints, and expose stress behavior.
It is not yet enough to claim superiority over established aircraft routing,
orbital analysis, or mission operations planning methods.

The most important remaining maturity work is to add richer benchmark scenarios,
clearer physical assumptions, comparisons against established methods, and at
least one genuinely hard optimization case where the unified planner's advantage
is obvious.
