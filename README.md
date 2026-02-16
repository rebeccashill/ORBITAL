🚀 ORBITAL
Unified Mission Planning Framework for Aircraft & Spacecraft

ORBITAL is a domain-agnostic mission planning framework that supports:

✈️ Aircraft multi-waypoint optimization

🛰️ Spacecraft 7-day scheduling & operations planning

🔁 Simulation-based optimization with constraints

📊 Monte Carlo robustness analysis

📁 Structured reporting (JSON, CSV exports)

The core idea:

One unified planning architecture.
Two different mission domains.
Zero domain duplication in the optimization engine.

🧠 Architecture Overview
mission_framework/
│
├── core/                # Unified domain-agnostic layer
│   ├── decision_variables.py
│   ├── constraints.py
│   ├── objective.py
│   ├── planner.py
│   ├── problem.py
│   ├── solution.py
│   └── types.py
│
├── simulation/          # Generic simulation utilities
│   ├── simulator.py
│   ├── feasibility.py
│   └── uncertainty.py
│
├── aircraft/            # MODULE A
│   ├── mission.py
│   ├── constraints.py
│   ├── objective.py
│   └── dynamics.py
│
├── spacecraft/          # MODULE B
│   ├── orbit.py
│   ├── visibility.py
│   ├── power.py
│   ├── attitude.py
│   ├── mission.py
│   ├── constraints.py
│   └── objective.py
│
├── reporting/
│   ├── flight_output.py
│   ├── schedule_output.py
│   ├── constraint_report.py
│   └── summary_metrics.py
│
├── examples/
│   ├── aircraft_uav_demo.yaml
│   └── cubesat_leo_demo.yaml
│
└── tests/
    ├── test_unified_architecture.py
    ├── test_aircraft_end_to_end.py
    └── test_spacecraft_end_to_end.py

🔬 Core Philosophy

ORBITAL separates:

1️⃣ Decision Space

What can change?

Continuous variables

Integer variables

Binary selections

Discrete options

Permutations

2️⃣ Simulation

What actually happens when we try it?

Aircraft dynamics propagation

Spacecraft orbit propagation

Battery simulation

Slew feasibility

Resource tracking

3️⃣ Constraints

What must not break?

Hard constraints (must pass)

Soft constraints (penalized)

4️⃣ Objective

What are we optimizing?

Minimize time

Minimize energy

Maximize science value

Minimize penalties

✈️ Aircraft Module

Features:

Multi-waypoint route optimization

Battery tracking

Geofence constraint

Mission completion constraint

Time + energy weighted objective

Run:

python -m mission_framework.cli examples/aircraft_uav_demo.yaml

🛰️ Spacecraft Module

7-Day CubeSat Earth Observation scenario:

Two-body orbit propagation

Ground target visibility windows

Ground station contact windows

Battery charge/discharge model

Slew-rate feasibility check

Cooldown constraints

Science value maximization

Monte Carlo robustness

Run:

python -m mission_framework.cli examples/cubesat_leo_demo.yaml


Faster test run:

python -m mission_framework.cli examples/cubesat_leo_demo.yaml --iterations 200 --restarts 1 --robustness 0

🧪 Testing

Run all tests:

pytest -q


Tests include:

Unified architecture validation

Aircraft end-to-end pipeline

Spacecraft end-to-end pipeline

Shared planner enforcement

📊 Example Output

Spacecraft summary example:

=== ORBITAL: Planning Complete ===
Scenario: CubeSat 7-Day Earth Observation Demo
Type:     spacecraft
Score:    -33
Feasible: True


Schedule export:

seq | etype       | label    | target_id | t_start_s | t_end_s
0   | observation | OBS_TGT1 | TGT1      | ...
1   | downlink    | DL_GS1   |           | ...

⚙️ Installation

Clone the repository:

git clone https://github.com/YOUR_USERNAME/orbital.git
cd orbital


Create virtual environment:

python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows


Install dependencies:

pip install -r requirements.txt

🧩 Why This Project Matters

ORBITAL demonstrates:

Simulation-based optimization

Mixed discrete/continuous search

Domain abstraction architecture

Aerospace mission systems thinking

Robustness evaluation under uncertainty

It is structured for:

Aerospace systems roles

Mission analysis engineering

Technical product roles

Advanced planning systems research

Enterprise aerospace account strategy understanding

🔮 Roadmap

Planned extensions:

Eclipse modeling

Data storage + volume tracking

Multi-satellite constellation planning

Parallelized Monte Carlo

More advanced search algorithms (CEM, GA, etc.)

Visualization dashboards

📄 License

MIT License
