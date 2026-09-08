# AeroHack 2026 Submission Checklist

## Required Components Status

### 1. Runnable Code

- Location: GitHub repository
- Language: Python 3.10+
- Structure:
  - `/mission_framework` - core planning engine and domain modules
  - `/examples` - aircraft and spacecraft demo configs
  - `/tests` - unit, architecture, and end-to-end tests
  - `/scripts` - validation and helper scripts

### 2. Reproducible Run Steps

- Location: `README.md`
- Exact commands:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python run_all.py --fast --no-plots
python -m mission_framework.cli examples/aircraft_uav_demo.yaml
python -m mission_framework.cli examples/cubesat_leo_demo.yaml
python scripts/run_validation.py
```

- Expected runtime: 2-15 minutes total, depending on robustness settings
- Output locations: `runs/<scenario>/` and `outputs/`

### 3. Results Bundle

Location: `/outputs`

Aircraft results in `outputs/aircraft/`:

- `waypoints.csv` - planned route with ETAs
- `constraints.json` - constraint check summary
- `score.json` - performance metrics
- `robustness.json` - Monte Carlo summary
- `run_log.txt` - console output
- `flight_path.png` - 2D flight trajectory visualization
- `battery_state.png` - battery energy plot
- `mission_overview.png` - combined mission dashboard

Key aircraft metrics:

- Mission time: 122 s
- Energy used: 7.45 Wh
- Geofence violations: 0
- Battery violations: 0

Spacecraft results in `outputs/spacecraft/`:

- `schedule.csv` - 7-day activity timeline
- `constraints.json` - constraint validation
- `score.json` - science value accounting
- `robustness.json` - Monte Carlo summary
- `run_log.txt` - console output
- `mission_timeline.png` - 7-day timeline visualization
- `operations_summary.png` - event type statistics
- `daily_activity.png` - daily operations distribution

Key spacecraft metrics:

- Observations: 3 targets captured
- Downlinks: 11 ground station contacts
- Science value: 33 points
- Hard pass rate: 100%

### 4. Technical Report PDF

- Location: `docs/AEROHACK_TECHNICAL_REPORT.md`
- PDF: `docs/AEROHACK_TECHNICAL_REPORT.pdf`
- Length: 8 pages equivalent
- Contents:
  - Problem statement for both domains
  - Modeling assumptions and equations
  - Constraints and objectives
  - Planning approach and justification
  - Validation method and results
  - Limitations and future work

### 5. Validation Evidence

Location: `scripts/run_validation.py`

Aircraft validation:

- Method: Monte Carlo wind uncertainty with 50 cases
- Aggregation: CVaR alpha=0.8 robust tail risk
- Result: consistent feasible solutions across wind seeds

Spacecraft validation:

- Method: Monte Carlo parameter perturbations with 30 cases
- Result: 100% hard pass rate in the baseline validation bundle
- Consistency: high, with feasible solutions found across validation runs

---

## Additional Artifacts

Documentation:

- `README.md` - project overview and quick start
- `docs/AEROHACK_TECHNICAL_REPORT.md` - full technical report
- `docs/SUBMISSION_CHECKLIST.md` - this checklist

Code quality:

- Unified architecture using the same planner for both domains
- Clean separation of concerns across `core`, `aircraft`, and `spacecraft`
- Type hints and docstrings
- MIT License

Examples:

- `examples/aircraft_uav_demo.yaml` - UAV mission config
- `examples/cubesat_leo_demo.yaml` - CubeSat mission config

---

## AeroHack Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Unified planning architecture | Complete | `mission_framework/core/planner.py` |
| Aircraft with wind | Complete | Stochastic wind model in `aircraft/model.py` |
| Aircraft with energy limits | Complete | Battery model in `aircraft/battery_model.py` |
| Aircraft with maneuver limits | Complete | Bank angle constraints in `aircraft/dynamics.py` |
| Aircraft with geofencing | Complete | Geofence validation in `aircraft/model.py` |
| Spacecraft orbit propagation | Complete | Two-body dynamics in `spacecraft/orbit.py` |
| Spacecraft visibility windows | Complete | Ground target visibility in `spacecraft/visibility.py` |
| Spacecraft slew feasibility | Complete | Attitude constraints in `spacecraft/attitude.py` |
| Spacecraft power budget | Complete | Battery model in `spacecraft/power.py` |
| Robustness validation | Complete | Monte Carlo in `scripts/run_validation.py` |
| Reproducible results | Complete | Exact commands in `README.md` |
| Technical documentation | Complete | Report in `docs/` |

---

## Submission Summary

Project name: ORBITAL - Unified Mission Planning Framework  
Team: Rebecca Shillingford  
Repository: https://github.com/rebeccashill/ORBITAL  
License: MIT  
Submission date: February 16, 2026

Unique value:

- Single planning engine handles both aircraft and spacecraft
- Demonstrates aerospace systems thinking across two operational domains
- Includes reproducible outputs, validation, plots, and documentation
- Provides a clear path from demo scenarios to stronger mission-planning experiments

Completeness: all listed AeroHack requirements are represented in the repository.
