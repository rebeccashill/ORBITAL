# 🚀 ORBITAL

**Operational Reusable Backend for Integrated Trajectory and
Logistics**\
Unified Mission Planning Framework for Aircraft & Spacecraft

ORBITAL is a domain-agnostic mission planning framework that supports:

-   ✈️ Aircraft multi-waypoint optimization
-   🛰️ Spacecraft 7-day scheduling & operations planning
-   🔁 Simulation-based optimization with constraints
-   📊 Monte Carlo robustness analysis
-   📁 Structured reporting (JSON, CSV exports)
-   📈 Automated visualization (flight paths, timelines, performance
    plots)

------------------------------------------------------------------------

# 🧪 Judge Quick Start (Reproducible in 3 Commands)

## 1️⃣ Install

``` bash
git clone https://github.com/rebeccashill/ORBITAL.git
cd ORBITAL
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows (PowerShell)
pip install -r requirements.txt
```

------------------------------------------------------------------------

## 2️⃣ Aircraft Demo (200 iterations)

``` bash
python -m mission_framework.cli examples/aircraft_uav_demo.yaml --iterations 200 --restarts 1 --robustness 20 --seed 0
```

Outputs saved to:

    runs/aircraft_uav_demo/

------------------------------------------------------------------------

## 3️⃣ Spacecraft Demo (200 iterations)

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

# 📄 License

MIT License\
Copyright (c) 2026 Rebecca Shillingford

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
