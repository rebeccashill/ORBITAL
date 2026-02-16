#!/usr/bin/env python3
"""
AeroHack Validation Script
Runs Monte Carlo analysis for both aircraft and spacecraft missions
to demonstrate robustness under uncertainty.
"""
import subprocess
import json
import sys
from pathlib import Path

def run_monte_carlo_aircraft(iterations: int = 500, restarts: int = 2, robustness_cases: int = 50):
    """Run aircraft demo with Monte Carlo wind uncertainty"""
    print(f"\n{'='*60}")
    print("AIRCRAFT VALIDATION - Monte Carlo Wind Uncertainty")
    print(f"{'='*60}\n")
    
    cmd = [
        sys.executable, "-m", "mission_framework.cli",
        "examples/aircraft_uav_demo.yaml",
        "--iterations", str(iterations),
        "--restarts", str(restarts),
        "--robustness", str(robustness_cases),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        return False
    
    # Copy results to validation folder
    runs_dir = Path("runs/aircraft_uav_demo")
    val_dir = Path("outputs/validation/aircraft")
    val_dir.mkdir(parents=True, exist_ok=True)
    
    for f in runs_dir.glob("*.json"):
        import shutil
        shutil.copy(f, val_dir / f.name)
    for f in runs_dir.glob("*.csv"):
        import shutil
        shutil.copy(f, val_dir / f.name)
    
    # Extract key metrics
    robustness_file = runs_dir / "robustness.json"
    if robustness_file.exists():
        with open(robustness_file) as f:
            rob_data = json.load(f)
        print(f"\n🎯 Aircraft Robustness Results:")
        print(f"   Cases tested: {rob_data['cases']}")
        print(f"   Hard pass rate: {rob_data['hard_pass_rate']*100:.1f}%")
        print(f"   Robust score (CVaR α=0.8): {rob_data['robust_score']:.2f}")
        print(f"   Mean score: {rob_data['mean_score']:.2f}")
        print(f"   Median score: {rob_data['p50_score']:.2f}")
        print(f"   P90 score: {rob_data['p90_score']:.2f}")
    
    return True

def run_monte_carlo_spacecraft(iterations: int = 300, restarts: int = 2, robustness_cases: int = 30):
    """Run spacecraft demo with Monte Carlo parameter uncertainty"""
    print(f"\n{'='*60}")
    print("SPACECRAFT VALIDATION - Monte Carlo Parameter Uncertainty")
    print(f"{'='*60}\n")
    
    cmd = [
        sys.executable, "-m", "mission_framework.cli",
        "examples/cubesat_leo_demo.yaml",
        "--iterations", str(iterations),
        "--restarts", str(restarts),
        "--robustness", str(robustness_cases),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        return False
    
    # Copy results to validation folder
    runs_dir = Path("runs/cubesat_leo_demo")
    val_dir = Path("outputs/validation/spacecraft")
    val_dir.mkdir(parents=True, exist_ok=True)
    
    for f in runs_dir.glob("*.json"):
        import shutil
        shutil.copy(f, val_dir / f.name)
    for f in runs_dir.glob("*.csv"):
        import shutil
        shutil.copy(f, val_dir / f.name)
    
    # Extract key metrics
    robustness_file = runs_dir / "robustness.json"
    if robustness_file.exists():
        with open(robustness_file) as f:
            rob_data = json.load(f)
        print(f"\n🎯 Spacecraft Robustness Results:")
        print(f"   Cases tested: {rob_data['cases']}")
        print(f"   Hard pass rate: {rob_data['hard_pass_rate']*100:.1f}%")
        print(f"   Robust score (CVaR α=0.8): {rob_data['robust_score']:.2f}")
        print(f"   Mean score: {rob_data['mean_score']:.2f}")
        print(f"   Median score: {rob_data['p50_score']:.2f}")
        print(f"   P90 score: {rob_data['p90_score']:.2f}")
    
    return True

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         AEROHACK VALIDATION - MONTE CARLO ANALYSIS        ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Run aircraft validation
    success_aircraft = run_monte_carlo_aircraft(
        iterations=500,
        restarts=2,
        robustness_cases=50
    )
    
    # Run spacecraft validation
    success_spacecraft = run_monte_carlo_spacecraft(
        iterations=300,
        restarts=2,
        robustness_cases=30
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Aircraft:   {'✓ PASS' if success_aircraft else '✗ FAIL'}")
    print(f"Spacecraft: {'✓ PASS' if success_spacecraft else '✗ FAIL'}")
    print(f"\nResults saved to: outputs/validation/")
    print(f"{'='*60}\n")
    
    return 0 if (success_aircraft and success_spacecraft) else 1

if __name__ == "__main__":
    sys.exit(main())
