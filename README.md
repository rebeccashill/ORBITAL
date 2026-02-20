# 🚀 ORBITAL

**Operational Reusable Backend for Integrated Trajectory and
Logistics**\
Unified Mission Planning Framework for Aircraft & Spacecraft

ORBITAL is a domain-agnostic mission planning framework that supports:

-   ✈️ Aircraft multi-waypoint optimization\
-   🛰️ Spacecraft 7-day scheduling & operations planning\
-   🔁 Simulation-based optimization with constraints\
-   📊 Monte Carlo robustness analysis\
-   📁 Structured reporting (JSON, CSV exports)\
-   📈 Automated visualization (flight paths, timelines, performance
    plots)

------------------------------------------------------------------------

# 🧪 Judge Quick Start (Reproducible in ONE Command)

## 1️⃣ Install

``` bash
git clone https://github.com/rebeccashill/ORBITAL.git
cd ORBITAL
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows (PowerShell)
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

------------------------------------------------------------------------

## 🚀 Run BOTH Domains (Primary Command)

``` bash
python run_all.py
```

Outputs saved to:

runs/aircraft_uav_demo/\
runs/cubesat_leo_demo/

------------------------------------------------------------------------

## 📦 Deliverables (Judge Quick Links)

-   **technical report (pdf, 4--8 pages):**
    `docs/AEROHACK_TECHNICAL_REPORT.pdf`
-   **results bundle:** `outputs/` (aircraft + spacecraft artifacts)
-   **reproduce results:** see sections below

------------------------------------------------------------------------

## 🔁 Individual Demo Commands (Optional)

### Aircraft Demo

``` bash
python -m mission_framework.cli examples/aircraft_uav_demo.yaml --iterations 200 --restarts 1 --robustness 20 --seed 0
```

Outputs saved to:

runs/aircraft_uav_demo/

------------------------------------------------------------------------

### Spacecraft Demo

``` bash
python -m mission_framework.cli examples/cubesat_leo_demo.yaml --iterations 200 --restarts 1 --robustness 10 --seed 0
```

Outputs saved to:

runs/cubesat_leo_demo/

------------------------------------------------------------------------

# 🧠 Architecture Overview

mission_framework/
├── core/
├── simulation/
├── aircraft/
├── spacecraft/
├── reporting/
├── visualization/
├── examples/
└── tests/

------------------------------------------------------------------------

# 🔬 Core Philosophy

ORBITAL separates four key concerns:

## Decision Space

Continuous, integer, binary, discrete, permutation variables.

## Simulation

Aircraft dynamics, orbit propagation, battery models, slew feasibility.

## Constraints

Hard constraints (must pass) and soft constraints (penalized via margin
discipline).

## Objective

Minimize time/energy or maximize science value in unified cost space.

------------------------------------------------------------------------

# 📊 Baseline Comparisons

``` bash
python scripts/run_baselines.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml
```

Outputs:

outputs/validation/baselines/

------------------------------------------------------------------------

# 🔥 Stress Tests

``` bash
python scripts/run_validation.py
```

Outputs:

outputs/validation/

Failure cases are automatically preserved.

------------------------------------------------------------------------

# 🌱 Multi-Seed Stability

``` bash
python experiments/run_seed_experiments.py --aircraft examples/aircraft_uav_demo.yaml --spacecraft examples/cubesat_leo_demo.yaml --seeds 20 --iterations 200 --restarts 1 --robustness 0 --out results/seed_runs.csv
```

------------------------------------------------------------------------

# ⏱ Expected Runtime

-   Aircraft demo: \~30--60 seconds\
-   Spacecraft demo: \~60--120 seconds\
-   Full validation suite: \~10--15 minutes

------------------------------------------------------------------------

# 🧪 Development & Quality Checks

``` bash
ruff check .
black --check .
mypy mission_framework
pytest
```

------------------------------------------------------------------------

# 📄 License

MIT License\
Copyright (c) 2026 Rebecca Shillingford
