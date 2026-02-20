# mission_framework/aircraft/objective.py
"""
Aircraft objectives (MODULE A / aircraft).

This module defines common optimization objectives for UAV missions, typically used
by a planner/optimizer after a simulation rollout.

Objectives here are "read-only": they only look at a simulation result and return
a scalar cost (lower is better).

Common objectives:
- Min time
- Min fuel / min energy
- Min distance (ground track length)
- Multi-objective weighted blend

Expected simulation result shape (flexible):
- sim.times or sim.timeline.t: sequence of timestamps
- sim.states: sequence of states with x,y,z,v (from aircraft/model.py)
- sim.fuel_initial / sim.fuel_remaining (optional)
- sim.energy_initial / sim.energy_remaining (optional)
- sim.metrics (optional) if you store precomputed metrics

If you want feasibility-aware shaping, combine with:
  mission_framework/simulation/feasibility.py  (shaped_score)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import math

# ============================================================
# Simulation extraction helpers
# ============================================================


def _times(sim) -> List[float]:
    t = getattr(sim, "times", None)
    if t is not None:
        return list(t)
    if hasattr(sim, "timeline") and hasattr(sim.timeline, "t"):
        return list(sim.timeline.t)
    raise AttributeError("Simulation result must have `times` or `timeline.t`.")


def _states(sim) -> List[object]:
    s = getattr(sim, "states", None)
    if s is None:
        raise AttributeError("Simulation result must have `states`.")
    return list(s)


def _fuel_used(sim) -> Optional[float]:
    if hasattr(sim, "fuel_used"):
        return float(getattr(sim, "fuel_used"))
    if hasattr(sim, "fuel_initial") and hasattr(sim, "fuel_remaining"):
        return float(getattr(sim, "fuel_initial")) - float(getattr(sim, "fuel_remaining"))
    return None


def _energy_used(sim) -> Optional[float]:
    if hasattr(sim, "energy_used"):
        return float(getattr(sim, "energy_used"))
    if hasattr(sim, "energy_initial") and hasattr(sim, "energy_remaining"):
        return float(getattr(sim, "energy_initial")) - float(getattr(sim, "energy_remaining"))
    return None


def _ground_distance(sim) -> float:
    sts = _states(sim)
    if len(sts) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(sts[:-1], sts[1:]):
        dx = float(getattr(b, "x")) - float(getattr(a, "x"))
        dy = float(getattr(b, "y")) - float(getattr(a, "y"))
        total += math.sqrt(dx * dx + dy * dy)
    return float(total)


# ============================================================
# Objective interface
# ============================================================

ObjectiveFn = Callable[[object], float]


@dataclass(frozen=True)
class Objective:
    """
    Wrapper for an objective function.
    Lower cost is better.

    name: identifier
    fn: function(sim) -> cost
    """

    name: str
    fn: ObjectiveFn

    def __call__(self, sim) -> float:
        return float(self.fn(sim))


# ============================================================
# Objective factories
# ============================================================


def min_time(*, name: str = "min_time") -> Objective:
    """Minimize total mission duration."""

    def _fn(sim) -> float:
        ts = _times(sim)
        if not ts:
            return 0.0
        return float(ts[-1] - ts[0])

    return Objective(name=name, fn=_fn)


def min_fuel(*, fallback_cost: float = 1e6, name: str = "min_fuel") -> Objective:
    """Minimize fuel used (requires sim to track fuel info)."""

    def _fn(sim) -> float:
        used = _fuel_used(sim)
        return float(used) if used is not None else float(fallback_cost)

    return Objective(name=name, fn=_fn)


def min_energy(*, fallback_cost: float = 1e6, name: str = "min_energy") -> Objective:
    """Minimize battery energy used (requires sim to track energy info)."""

    def _fn(sim) -> float:
        used = _energy_used(sim)
        return float(used) if used is not None else float(fallback_cost)

    return Objective(name=name, fn=_fn)


def min_distance(*, name: str = "min_distance") -> Objective:
    """Minimize ground-track distance."""

    def _fn(sim) -> float:
        return _ground_distance(sim)

    return Objective(name=name, fn=_fn)


# ============================================================
# Weighted blends
# ============================================================


@dataclass(frozen=True)
class WeightedObjective(Objective):
    """
    Weighted blend of multiple objective terms.
    """

    terms: Tuple[Tuple[str, ObjectiveFn, float], ...]  # (term_name, fn, weight)

    def __call__(self, sim) -> float:
        total = 0.0
        for _, fn, w in self.terms:
            total += float(w) * float(fn(sim))
        return float(total)

    def breakdown(self, sim) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for term_name, fn, w in self.terms:
            out[term_name] = float(w) * float(fn(sim))
        out["total"] = float(sum(out.values()))
        return out


def weighted_blend(
    *,
    w_time: float = 1.0,
    w_fuel: float = 0.0,
    w_energy: float = 0.0,
    w_distance: float = 0.0,
    fuel_fallback: float = 1e6,
    energy_fallback: float = 1e6,
    name: str = "weighted_blend",
) -> WeightedObjective:
    """
    Create a weighted blend objective.

    Example:
        obj = weighted_blend(w_time=1.0, w_energy=0.001)
    """
    terms: List[Tuple[str, ObjectiveFn, float]] = []

    if w_time != 0.0:
        terms.append(("time", min_time().fn, float(w_time)))
    if w_fuel != 0.0:
        terms.append(("fuel", min_fuel(fallback_cost=fuel_fallback).fn, float(w_fuel)))
    if w_energy != 0.0:
        terms.append(("energy", min_energy(fallback_cost=energy_fallback).fn, float(w_energy)))
    if w_distance != 0.0:
        terms.append(("distance", min_distance().fn, float(w_distance)))

    return WeightedObjective(name=name, fn=lambda sim: 0.0, terms=tuple(terms))
