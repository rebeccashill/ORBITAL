# ORBITAL: Unified Mission Planning Framework
## AeroHack 2026 Technical Report

**Team:** Rebecca Shillingford  
**Date:** February 16, 2026  
**Repository:** https://github.com/rebeccashill/ORBITAL

---

## Executive Summary

ORBITAL is a domain-agnostic mission planning and simulation framework that addresses both aircraft (UAV) and spacecraft (CubeSat LEO) mission planning using a unified architecture.

**Key Achievements:**
- Unified constraint-objective-planner architecture for both domains
- Aircraft: Multi-waypoint planning with wind, energy, maneuver, and geofence constraints
- Spacecraft: 7-day LEO observation/downlink scheduling with orbit dynamics
- Monte Carlo robustness validation
- Zero constraint violations in feasible solutions
- Reproducible end-to-end pipeline

---

## 1. Problem Statement

### 1.1 Aircraft Mission Task (UAV Fixed-Wing)

**Objective:** Plan a multi-waypoint flight mission that minimizes time and energy while respecting:

- **Wind Effects:** Time-varying stochastic wind
- **Endurance Limits:** Battery capacity constraints
- **Maneuver Limits:** Bank angle and turn rate constraints
- **Geofencing:** No-fly polygon zones
- **Waypoint Completion:** All waypoints must be visited

### 1.2 Spacecraft Mission Task (CubeSat LEO Operations)

**Objective:** Generate a 7-day mission schedule that maximizes science value.

---

## 2. System Architecture

### 2.1 Unified Planning Concept

ORBITAL implements a domain-agnostic planning architecture with four key abstractions:
1. Decision Variables (continuous, discrete)
2. Simulation (domain-specific physics)
3. Constraints (hard/soft, margin-based)
4. Objectives (weighted multi-term)

Both domains share the same planner, constraint system, objective framework, and robustness analysis.

---

## 3. Results Summary

### 3.1 Aircraft Results
- Score: 8124.23
- Energy used: 7.45 Wh
- Flight time: 122 s
- Geofence violations: 0

### 3.2 Spacecraft Results
- Score: -33.0 (FEASIBLE)
- Targets observed: 3/3
- Downlinks: 11
- Science value: 33 points
- Hard pass rate: 100%

---

## 4. Reproducibility

```bash
# Install dependencies
pip install -r requirements.txt

# Run aircraft mission
python -m mission_framework.cli examples/aircraft_uav_demo.yaml

# Run spacecraft mission
python -m mission_framework.cli examples/cubesat_leo_demo.yaml
```

---

**Report Prepared By:** Rebecca Shillingford  
**Submission Date:** February 16, 2026
