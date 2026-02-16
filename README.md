🚀 ORBITAL
Unified Aircraft & Spacecraft Mission Planning Framework








Constraint-based mission planning architecture for UAV and CubeSat operations using a single reusable optimization core.

📌 Overview

ORBITAL is a domain-agnostic mission planning and simulation framework designed to demonstrate systems-level aerospace architecture.

It provides:

🧮 Unified decision variable system

📏 Constraint evaluation framework

🎯 Objective-based optimization

🔁 Simulation-in-the-loop planning

✅ Feasibility verification

📊 Monte Carlo robustness analysis

Two distinct domains are supported using the same planning engine:

Domain	Capability
✈ Aircraft	UAV route optimization with wind, energy, geofencing
🛰 Spacecraft	7-day CubeSat LEO scheduling with power, slew & downlink constraints

One architecture. Two physical domains. Shared optimization core.

🧠 Architectural Philosophy

ORBITAL enforces strict separation of concerns:

Decision Variables
        ↓
Unified Planner (stochastic optimization)
        ↓
Executable Plan
        ↓
Simulation
        ↓
Constraint Evaluation
        ↓
Objective Scoring
        ↓
Robustness Analysis

Core Principle

The planner is domain-agnostic.

Each domain module defines only:

Its physics model

Its domain constraints

Its mission configuration

Everything else — planning, scoring, constraint logic — is shared.

📂 Project Structure
mission_framework/
├── core/           # Unified decision + constraint + objective system
├── simulation/     # Simulation harness + uncertainty tools
├── aircraft/       # UAV mission module
├── spacecraft/     # CubeSat mission module
├── reporting/      # Output formatting and exports
└── cli.py          # Command-line entry point

✈ Module A — Aircraft (UAV)
Capabilities

Ordered waypoint route planning

Point-mass kinematic simulation

Time-varying wind field model

Battery / energy consumption model

Turn-rate / maneuver constraints

Geofencing (polygon no-fly zones)

Minimum-time or minimum-energy optimization

Monte Carlo wind robustness

Outputs

Time-stamped trajectory

Constraint evaluation report

Energy and time metrics

Robustness summary statistics

🛰 Module B — Spacecraft (CubeSat LEO)
Capabilities

Two-body orbital propagation

Ground target visibility windows

Ground station contact windows

7-day event schedule construction

Slew-rate feasibility modeling

Battery charge/discharge proxy model

Cooldown & operations-per-orbit limits

Science value maximization objective

Outputs

7-day schedule

Contact window evidence

Constraint feasibility report

Delivered science value metrics

Robustness summary

⚙ Unified Planning Method

The planner uses simulation-based stochastic optimization:

Sample candidate decision assignments

Build executable plan

Simulate mission execution

Evaluate constraint margins

Compute objective cost

Apply penalty shaping

Iterate

Supported Decision Types

Continuous

Integer

Binary

Discrete

Permutation

📏 Constraint System

Each constraint returns a margin value:

Margin	Meaning
≥ 0	Constraint satisfied
< 0	Constraint violated

This enables:

Hard vs soft constraint separation

Penalty shaping

Robustness statistics

Worst-case margin tracking

🎯 Objective Framework

All objectives reduce to a scalar cost:

Minimize time

Minimize energy

Maximize mission value (converted internally to cost)

Supports weighted multi-objective trade studies.

🔁 Robustness Evaluation

Plans may be evaluated under uncertainty:

Wind variation

Battery capacity variation

Slew-rate variation

Contact timing jitter

Reported metrics:

Hard feasibility rate

Worst-case constraint margin

Mean objective score

P50 / P90 percentiles

▶ Running ORBITAL
🔧 Installation
pip install -r requirements.txt

✈ Run Aircraft Demo
python -m mission_framework.cli examples/aircraft_uav_demo.yaml

🛰 Run Spacecraft Demo
python -m mission_framework.cli examples/cubesat_leo_demo.yaml

Optional CLI Flags
--iterations 200
--restarts 1
--robustness 0


Example:

python -m mission_framework.cli examples/cubesat_leo_demo.yaml --iterations 200 --restarts 1 --robustness 0

📊 Example Use Cases
UAV

Autonomous inspection routing

Energy-constrained delivery optimization

Wind-robust path planning

CubeSat

Earth observation scheduling

Downlink optimization

Power-constrained mission design

Trade studies under uncertainty

🏗 Engineering Principles Demonstrated

Systems-level architecture design

Separation of planning vs simulation

Constraint-based reasoning

Mixed discrete/continuous optimization

Robust validation under uncertainty

Cross-domain abstraction

Reusable aerospace software design

🔭 Future Extensions

6-DOF aircraft dynamics

J2 perturbation & drag modeling

MILP / hybrid solver backend

Parallel Monte Carlo execution

Visualization dashboard

Multi-vehicle coordination

📄 License

MIT License


