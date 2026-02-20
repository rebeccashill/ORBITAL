# Baseline Comparisons (AeroHack Validation)

This document provides baseline comparisons for both mission domains to support the
**Robustness & Validation** rubric category.

## Why baselines?

A baseline answers: **“What happens if we *don’t* run the optimizer?”**

We compare ORBITAL against simple non-optimized strategies using the same
simulation + constraint + objective pipeline.

For the spacecraft scenario, best-of-50 random sampling achieved a comparable or slightly better score than a single 200-iteration ORBITAL run.

This indicates the search landscape is relatively smooth for the simplified demonstration case.

In higher-fidelity or more constrained scenarios, iterative mutation-based search is expected to provide greater advantage.

## Methods

### Aircraft baseline — Random feasible (no optimization)
- **Definition:** run **one** randomly sampled feasible assignment (no mutation, no search).
- **Config:** `iterations=0`, `restarts=1`, `robustness=0`
- **Purpose:** establishes a “no optimizer” reference point.

### Spacecraft baseline — Best-of-K sampling (greedy-ish)
- **Definition:** sample **K** random feasible assignments, pick the best score.
- **Config:** `iterations=0`, `restarts=K` (default K=50), `robustness=0`
- **Purpose:** shows how much ORBITAL improves beyond “try a bunch of random schedules.”

## How to reproduce

```powershell
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --out outputs/validation/baselines/baselines.csv