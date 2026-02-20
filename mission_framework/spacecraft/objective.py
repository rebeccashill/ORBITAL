# mission_framework/spacecraft/objective.py
"""
Spacecraft objective helpers (MODULE B).

This module defines objective terms that are specific to CubeSat-style LEO ops
but plug into the domain-agnostic core Objective system.

Typical spacecraft objective:
- Maximize delivered science value (observations that are successfully downlinked)
- Penalize missed downlinks / undelivered observations
- Optionally penalize power risk (low min battery)
- Optionally penalize aggressive scheduling (too many ops per orbit, etc.)

Important:
- The unified framework always *minimizes cost*.
- So "maximize value" terms are created with is_cost=False (core negates them into cost space).

The spacecraft mission simulator (spacecraft/mission.py) should expose the following scalars:
- mission_value: total delivered value (higher better)
- obs_scheduled: how many observations were scheduled
- obs_delivered: how many were delivered (downlinked)
- min_battery_Wh: minimum battery during horizon
- slew_margin_s: minimum slew feasibility margin (>=0 feasible)

This file provides convenience terms that safely pull those scalars from SimResult.
"""

from __future__ import annotations

from typing import Any, Optional

from mission_framework.core.objective import FunctionalObjectiveTerm


def _get_scalar(sim: Any, key: str, default: Optional[float] = None) -> float:
    # Works with core SimResult (preferred) or dict-like sims
    if hasattr(sim, "scalars") and isinstance(getattr(sim, "scalars"), dict):
        scalars = getattr(sim, "scalars")
        if key in scalars:
            return float(scalars[key])
    if hasattr(sim, key):
        return float(getattr(sim, key))
    if isinstance(sim, dict) and key in sim:
        return float(sim[key])
    if default is None:
        raise KeyError(f"Simulation result missing scalar '{key}' for spacecraft objective term.")
    return float(default)


# ============================================================
# Primary value terms
# ============================================================


def term_maximize_delivered_value(
    name: str = "delivered_value",
    weight: float = 1.0,
    key: str = "mission_value",
) -> FunctionalObjectiveTerm:
    """
    Maximize delivered mission value (higher is better).
    """

    def fn(sim: Any) -> float:
        return float(_get_scalar(sim, key))

    return FunctionalObjectiveTerm(name=name, fn=fn, weight=weight, is_cost=False)


def term_penalize_undelivered_observations(
    name: str = "undelivered_obs",
    weight: float = 1.0,
    scheduled_key: str = "obs_scheduled",
    delivered_key: str = "obs_delivered",
) -> FunctionalObjectiveTerm:
    """
    Penalize scheduled observations that were not delivered (downlinked).

    cost = max(0, scheduled - delivered)
    """

    def fn(sim: Any) -> float:
        scheduled = float(_get_scalar(sim, scheduled_key, 0.0))
        delivered = float(_get_scalar(sim, delivered_key, 0.0))
        return float(max(0.0, scheduled - delivered))

    return FunctionalObjectiveTerm(name=name, fn=fn, weight=weight, is_cost=True)


# ============================================================
# Risk / proxy penalty terms
# ============================================================


def term_penalize_low_battery(
    name: str = "battery_risk",
    weight: float = 0.1,
    min_batt_key: str = "min_battery_Wh",
    threshold_Wh: float = 5.0,
) -> FunctionalObjectiveTerm:
    """
    Soft risk penalty: encourage staying above a battery reserve.

    cost = max(0, threshold - min_battery_Wh)
    """

    def fn(sim: Any) -> float:
        min_batt = float(_get_scalar(sim, min_batt_key, 0.0))
        return float(max(0.0, float(threshold_Wh) - min_batt))

    return FunctionalObjectiveTerm(name=name, fn=fn, weight=weight, is_cost=True)


def term_penalize_tight_slew_margin(
    name: str = "slew_risk",
    weight: float = 0.05,
    slew_margin_key: str = "slew_margin_s",
    reserve_s: float = 5.0,
) -> FunctionalObjectiveTerm:
    """
    Soft risk penalty: encourage having some slack in slew feasibility.

    cost = max(0, reserve - slew_margin_s)
    """

    def fn(sim: Any) -> float:
        m = float(_get_scalar(sim, slew_margin_key, 0.0))
        return float(max(0.0, float(reserve_s) - m))

    return FunctionalObjectiveTerm(name=name, fn=fn, weight=weight, is_cost=True)
