# mission_framework/spacecraft/constraints.py
"""
Spacecraft constraints (MODULE B).

These are "wrappers" around the domain-agnostic core constraint interface, but
implemented using spacecraft simulation outputs (SimResult scalars/resources).

Constraints included (minimum viable + credible):
- battery_nonnegative (HARD): min battery >= 0 Wh
- slew_feasible (HARD): slew_margin_s >= 0 (can rotate between tasks fast enough)
- max_ops_per_orbit (SOFT, optional): avoid too many operations per orbit-ish period
- cooldown_between_observations (SOFT, optional): enforce time between successive observations (proxy)

This module returns constraints as core.Constraint objects so the same Planner works for both domains.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from mission_framework.core.constraints import (
    Constraint,
    FunctionalConstraint,
    Severity,
)
from mission_framework.core.types import SimResult


def _get_scalar(sim: Any, key: str, default: Optional[float] = None) -> float:
    """
    Pull a scalar from SimResult.scalars or attributes/dicts.
    """
    if isinstance(sim, SimResult):
        if key in sim.scalars:
            return float(sim.scalars[key])
    if hasattr(sim, key):
        v = getattr(sim, key)
        return float(v)
    if isinstance(sim, dict) and key in sim:
        return float(sim[key])
    if default is None:
        raise KeyError(f"Simulation missing scalar '{key}'")
    return float(default)


def _get_resource(sim: Any, key: str) -> np.ndarray:
    if isinstance(sim, SimResult):
        if key in sim.resources:
            return np.asarray(sim.resources[key], dtype=float)
    if isinstance(sim, dict) and key in sim:
        return np.asarray(sim[key], dtype=float)
    raise KeyError(f"Simulation missing resource '{key}'")


# ============================================================
# Individual constraint constructors
# ============================================================


def constraint_battery_nonnegative(
    *,
    key_min_batt: str = "min_battery_Wh",
    severity: Severity = Severity.HARD,
) -> Constraint:
    """
    HARD constraint: minimum battery must be >= 0.
    Margin = min_battery_Wh.
    """

    def margin(sim: Any) -> float:
        return float(_get_scalar(sim, key_min_batt))

    return FunctionalConstraint(
        name="battery_nonnegative",
        severity=severity,
        fn=margin,
        metadata={"key": key_min_batt, "meaning": "min battery must be >= 0 Wh"},
    )


def constraint_slew_feasible(
    *,
    key_margin: str = "slew_margin_s",
    severity: Severity = Severity.HARD,
) -> Constraint:
    """
    HARD constraint: slew margin must be >= 0 seconds.
    Margin = slew_margin_s (min gap - required slew+settle).
    """

    def margin(sim: Any) -> float:
        return float(_get_scalar(sim, key_margin))

    return FunctionalConstraint(
        name="slew_feasible",
        severity=severity,
        fn=margin,
        metadata={"key": key_margin, "meaning": "slew feasibility margin (s) must be >= 0"},
    )


def constraint_max_ops_per_orbit_soft(
    *,
    ops_key: str = "ops_per_orbit_max",
    orbit_period_s: float = 5400.0,
    max_ops: int = 6,
    severity: Severity = Severity.SOFT,
) -> Constraint:
    """
    SOFT constraint: limit max number of operations per orbit-ish interval.

    This is a proxy constraint that encourages realistic duty cycling and avoids
    "spam scheduling" in a simplified model.

    We compute:
      - divide horizon into bins of orbit_period_s
      - count events marked as observe/downlink (from metadata if provided)
    But since we only see SimResult here, we use a scalar if the mission sim computes it.
    If not present, this returns a very permissive constraint (margin=+inf).

    Margin = max_ops - ops_per_orbit_max
    """

    def margin(sim: Any) -> float:
        # If sim provides it, enforce; otherwise no-op (pass).
        try:
            ops = float(_get_scalar(sim, ops_key))
        except KeyError:
            return float("inf")
        return float(max_ops - ops)

    return FunctionalConstraint(
        name="max_ops_per_orbit",
        severity=severity,
        fn=margin,
        metadata={"key": ops_key, "max_ops": int(max_ops), "orbit_period_s": float(orbit_period_s)},
    )


def constraint_observation_cooldown_soft(
    *,
    cooldown_violation_key: str = "cooldown_violation_s",
    severity: Severity = Severity.SOFT,
) -> Constraint:
    """
    SOFT constraint: cooldown between observations.

    If sim computes a scalar "cooldown_violation_s" as the *maximum* violation in seconds,
    margin = -cooldown_violation_s (>=0 means no violation).
    If scalar missing, constraint is permissive (pass).
    """

    def margin(sim: Any) -> float:
        try:
            v = float(_get_scalar(sim, cooldown_violation_key))
        except KeyError:
            return float("inf")
        return float(-v)

    return FunctionalConstraint(
        name="cooldown_between_observations",
        severity=severity,
        fn=margin,
        metadata={"key": cooldown_violation_key, "meaning": "margin>=0 => cooldown satisfied"},
    )


# ============================================================
# Default set
# ============================================================


def default_spacecraft_constraints(cfg: Optional[Dict[str, Any]] = None) -> List[Constraint]:
    """
    Build the default spacecraft constraint set using optional config values.

    cfg fields (optional):
      power.min_Wh
      attitude.max_slew_rate_deg_s / settle_time_s (used in sim, not here)
      ops.max_ops_per_orbit
      ops.orbit_period_s
    """
    cfg = cfg or {}
    power_cfg = cfg.get("power", {}) or {}
    ops_cfg = cfg.get("ops", {}) or {}

    max_ops = int(ops_cfg.get("max_ops_per_orbit", 6))
    orbit_period_s = float(ops_cfg.get("orbit_period_s", 5400.0))

    constraints: List[Constraint] = [
        constraint_battery_nonnegative(key_min_batt="min_battery_Wh", severity=Severity.HARD),
        constraint_slew_feasible(key_margin="slew_margin_s", severity=Severity.HARD),
        constraint_max_ops_per_orbit_soft(
            ops_key="ops_per_orbit_max",
            orbit_period_s=orbit_period_s,
            max_ops=max_ops,
            severity=Severity.SOFT,
        ),
        constraint_observation_cooldown_soft(
            cooldown_violation_key="cooldown_violation_s",
            severity=Severity.SOFT,
        ),
    ]
    return constraints
