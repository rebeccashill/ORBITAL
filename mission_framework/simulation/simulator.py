"""mission_framework/simulation/simulator.py
Domain-agnostic simulation harness.

This module is intentionally lightweight.

Why?
- Aircraft and spacecraft have very different physics and execution semantics.
- The unified architecture requirement is met by sharing the *interfaces* and
  evaluation pipeline (plan -> simulate -> constraints -> objective -> robustness),
  not by forcing both domains into one monolithic physics engine.

So this file provides:
- A small Simulator wrapper around a domain-provided simulate(plan, rng)->SimResult
- Basic validation of returned SimResult
- Convenience helpers for robustness / Monte Carlo runs

Domain-specific propagation lives in:
- mission_framework/aircraft/model.py (+ wind/energy/geofence)
- mission_framework/spacecraft/orbit.py (+ visibility/power/attitude)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from mission_framework.core.types import SimResult, Plan


SimulateFn = Callable[[Plan, Optional[np.random.Generator]], SimResult]


@dataclass
class SimulatorConfig:
    """
    Config for the harness layer (not the domain physics).

    - validate: run basic checks on SimResult contents
    """
    validate: bool = True


class Simulator:
    """
    Wraps a domain-specific simulation function.

    The domain simulation function must accept:
        simulate(plan: Plan, rng: Optional[np.random.Generator]) -> SimResult

    and should be deterministic with respect to rng.
    """

    def __init__(self, simulate_fn: SimulateFn, cfg: SimulatorConfig = SimulatorConfig()):
        self.simulate_fn = simulate_fn
        self.cfg = cfg

    def run(self, plan: Plan, seed: Optional[int] = None, rng: Optional[np.random.Generator] = None) -> SimResult:
        """
        Run a single simulation.

        Provide either:
        - seed (int) to construct an RNG
        - rng directly (np.random.Generator)

        If both are None, simulation runs without a RNG (deterministic unless the
        domain model uses its own randomness).
        """
        if rng is None and seed is not None:
            rng = np.random.default_rng(int(seed))

        sim = self.simulate_fn(plan, rng)

        if self.cfg.validate:
            self._validate(sim)

        return sim

    def run_many(self, plan: Plan, seeds: Sequence[int]) -> List[SimResult]:
        """Run multiple simulations (Monte Carlo / robustness seeds)."""
        out: List[SimResult] = []
        for s in seeds:
            out.append(self.run(plan, seed=int(s)))
        return out

    def run_robustness(
        self,
        plan: Plan,
        cases: int,
        seed0: int = 0,
        stride: int = 10007,
    ) -> List[SimResult]:
        """
        Convenience: generate a deterministic list of seeds and run them.

        This is useful when you want reproducible robustness runs without passing
        an explicit seed list.
        """
        seeds = [int(seed0 + i * stride) for i in range(int(cases))]
        return self.run_many(plan, seeds)

    # -------------------------
    # Validation
    # -------------------------

    @staticmethod
    def _validate(sim: SimResult) -> None:
        """
        Basic checks to catch common integration bugs early.

        Requirements:
        - sim.t exists and is 1D
        - resources arrays match length of t
        - trajectory.t matches sim.t length if present
        """
        if sim is None:
            raise ValueError("simulate_fn returned None; expected SimResult.")

        t = np.array(sim.t, dtype=float).reshape(-1)
        if t.ndim != 1 or t.size < 1:
            raise ValueError("SimResult.t must be a non-empty 1D array.")
        if np.any(~np.isfinite(t)):
            raise ValueError("SimResult.t contains non-finite values.")

        # Ensure time is non-decreasing
        if np.any(np.diff(t) < -1e-12):
            raise ValueError("SimResult.t must be non-decreasing.")

        # Resource traces
        for k, v in sim.resources.items():
            arr = np.array(v, dtype=float).reshape(-1)
            if arr.shape[0] != t.shape[0]:
                raise ValueError(f"SimResult.resources['{k}'] length must match len(t).")
            if np.any(~np.isfinite(arr)):
                raise ValueError(f"SimResult.resources['{k}'] contains non-finite values.")

        # Trajectory alignment (if used)
        if sim.trajectory is not None:
            tt = np.array(sim.trajectory.t, dtype=float).reshape(-1)
            if tt.shape[0] != t.shape[0]:
                raise ValueError("SimResult.trajectory.t length must match SimResult.t length.")

        # Scalars must be finite numbers
        for k, v in sim.scalars.items():
            if not np.isfinite(float(v)):
                raise ValueError(f"SimResult.scalars['{k}'] is not finite.")

    # -------------------------
    # Utility
    # -------------------------

    @staticmethod
    def seed_sequence(seed0: int, n: int, stride: int = 10007) -> List[int]:
        """Deterministic seed generation helper."""
        return [int(seed0 + i * stride) for i in range(int(n))]


# ---------------------------
# Functional helpers (optional)
# ---------------------------

def simulate_once(simulate_fn: SimulateFn, plan: Plan, seed: Optional[int] = None) -> SimResult:
    """One-off helper without constructing a Simulator object."""
    sim = Simulator(simulate_fn).run(plan, seed=seed)
    return sim
