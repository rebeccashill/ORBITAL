# ORBITAL

[![CI](https://github.com/rebeccashill/ORBITAL/actions/workflows/ci.yml/badge.svg)](https://github.com/rebeccashill/ORBITAL/actions/workflows/ci.yml)

**Operational Reusable Backend for Integrated Trajectory and Logistics**  
Unified Mission Planning Framework for Aircraft and Spacecraft

ORBITAL is a domain-agnostic mission planning framework that supports:

- Aircraft multi-waypoint optimization
- Spacecraft 7-day scheduling and operations planning
- Simulation-based optimization with constraints
- Monte Carlo robustness analysis
- Structured reporting with JSON and CSV exports
- Automated visualization for flight paths, timelines, and performance plots

---

## Judge Quick Start

### 1. Install

```bash
git clone https://github.com/rebeccashill/ORBITAL.git
cd ORBITAL
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows PowerShell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Run Both Domains

```bash
python run_all.py
```

For a quick smoke run:

```bash
python run_all.py --fast
```

Outputs are saved to:

```text
runs/aircraft_uav_demo/
runs/cubesat_leo_demo/
```

### 3. Validate Scenario YAML

```bash
python -m mission_framework.cli validate examples/aircraft_uav_demo.yaml
python -m mission_framework.cli validate examples/cubesat_leo_demo.yaml
```

Installed CLI equivalent:

```bash
orbital validate examples/aircraft_uav_demo.yaml
```

See [Scenario Authoring Guide](docs/SCENARIO_AUTHORING.md) for YAML structure, units, examples, and common validation errors.

### 4. Optional Individual Demo Commands

Aircraft:

```bash
python -m mission_framework.cli examples/aircraft_uav_demo.yaml --iterations 200 --restarts 1 --robustness 20 --seed 0
```

Spacecraft:

```bash
python -m mission_framework.cli examples/cubesat_leo_demo.yaml --iterations 200 --restarts 1 --robustness 10 --seed 0
```

Use `--no-plots` when you only want JSON/CSV artifacts:

```bash
python run_all.py --fast --no-plots
```

---

## Deliverables

- Technical report PDF: `docs/AEROHACK_TECHNICAL_REPORT.pdf`
- Results bundle: `outputs/`
- Reproducible outputs: `runs/` after executing `python run_all.py`

---

## Architecture Overview

```text
mission_framework/
  core/            Shared decision variables, constraints, objectives, planner
  simulation/      Feasibility, metrics, uncertainty utilities
  aircraft/        UAV mission model, dynamics, energy, wind, geofence checks
  spacecraft/      CubeSat orbit, visibility, attitude, power, scheduling
  reporting/       CSV and text output helpers
  visualization/   Aircraft and spacecraft plots
examples/          Demo YAML scenarios
tests/             Architecture, frame, and end-to-end tests
```

ORBITAL separates four concerns:

- Decision space: continuous, integer, binary, discrete, and permutation variables
- Simulation: aircraft dynamics, orbit propagation, battery models, and slew feasibility
- Constraints: hard constraints for feasibility and soft constraints for penalties
- Objective: minimize time/energy or maximize science value in a unified score space

---

## Baseline Comparisons

```bash
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml
```

Outputs:

```text
outputs/validation/baselines/
```

The report compares ORBITAL against `random_search`, `greedy_routing`, and
`earliest_deadline` baselines across score, feasibility, runtime, and robustness.
See `docs/BASELINE_COMPARISONS.md` for the current summarized results.

---

## Stress Tests

```bash
python scripts/run_validation.py
```

Outputs:

```text
outputs/validation/
```

Failure cases are preserved for review.

---

## Multi-Seed Stability

```bash
python experiments/run_seed_experiments.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --seeds 20 --iterations 200 --restarts 1 --robustness 0 --out results/seed_runs.csv
```

---

## Expected Runtime

- Aircraft demo: about 30-60 seconds
- Spacecraft demo: about 60-120 seconds
- Full validation suite: about 10-15 minutes

---

## Development Checks

```bash
ruff check .
black --check .
mypy mission_framework
pytest
python run_all.py --fast --no-plots
```

---

## License

MIT License  
Copyright (c) 2026 Rebecca Shillingford
