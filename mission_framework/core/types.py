# mission_framework/core/types.py
"""
Core domain-agnostic types.

These types are deliberately minimal and flexible so BOTH domains can use them:
- Aircraft: produces a Trajectory (states over time) + Actions (waypoints/segments)
- Spacecraft: produces a Schedule (time-ordered events) + optional state history

The planner/simulator can store richer domain-specific objects in `metadata`
without breaking the unified architecture requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

# ---------------------------
# Time handling
# ---------------------------


@dataclass(frozen=True)
class TimeGrid:
    """
    Discrete time grid used by simulators.
    - t0: start time in seconds (arbitrary reference; often 0)
    - dt: step size in seconds
    - steps: number of steps (N), producing N+1 time points including t0
    """

    t0: float
    dt: float
    steps: int

    def times(self) -> np.ndarray:
        return self.t0 + self.dt * np.arange(self.steps + 1, dtype=float)

    @property
    def t_end(self) -> float:
        return self.t0 + self.dt * float(self.steps)


# ---------------------------
# Basic geometric primitives (optional convenience)
# ---------------------------


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


# ---------------------------
# Trajectory container (aircraft-friendly, but domain-agnostic)
# ---------------------------


@dataclass
class Trajectory:
    """
    Time-indexed state history.

    `state` is a (T, D) array (T time points, D state dimension).
    `control` is optional (T, U) or (T-1, U), depending on convention.

    The simulator decides what each dimension means; constraints/objectives
    read fields by name or via metadata.
    """

    t: np.ndarray  # shape (T,)
    state: np.ndarray  # shape (T, D)
    control: Optional[np.ndarray] = None  # shape (T, U) or (T-1, U)
    frame: str = "unspecified"  # e.g., "ENU", "NED", "ECI", "LVLH"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.t = np.array(self.t, dtype=float).reshape(-1)
        self.state = np.array(self.state, dtype=float)
        if self.control is not None:
            self.control = np.array(self.control, dtype=float)
        if self.state.shape[0] != self.t.shape[0]:
            raise ValueError("Trajectory.state must have same first dimension as t.")

    @property
    def T(self) -> int:
        return int(self.t.shape[0])

    @property
    def dim(self) -> int:
        return int(self.state.shape[1]) if self.state.ndim == 2 else 0

    def slice(self, i0: int, i1: int) -> "Trajectory":
        return Trajectory(
            t=self.t[i0:i1],
            state=self.state[i0:i1],
            control=None if self.control is None else self.control[i0:i1],
            frame=self.frame,
            metadata=dict(self.metadata),
        )


# ---------------------------
# Schedule container (spacecraft-friendly, but domain-agnostic)
# ---------------------------


class EventType(str, Enum):
    OBSERVATION = "observation"
    DOWNLINK = "downlink"
    SLEW = "slew"
    COOLDOWN = "cooldown"
    IDLE = "idle"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Event:
    """
    A time-ordered event for scheduling problems.

    Times are seconds since some reference epoch (kept consistent within a scenario).
    """

    t_start: float
    t_end: float
    etype: EventType
    label: str = ""
    target_id: Optional[str] = None
    location: Optional[Tuple[float, float]] = None  # lat, lon if relevant
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return float(self.t_end - self.t_start)


@dataclass
class Schedule:
    """A list of events in time order."""

    events: List[Event] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def sorted(self) -> "Schedule":
        return Schedule(
            events=sorted(self.events, key=lambda e: e.t_start), metadata=dict(self.metadata)
        )

    def validate_non_overlapping(self) -> None:
        ev = self.sorted().events
        for i in range(1, len(ev)):
            if ev[i].t_start < ev[i - 1].t_end - 1e-9:
                raise ValueError(f"Overlapping events: '{ev[i-1].label}' and '{ev[i].label}'")

    def window(self, t0: float, t1: float) -> List[Event]:
        return [e for e in self.events if (e.t_end > t0 and e.t_start < t1)]


# ---------------------------
# Plan object (unified "what to execute")
# ---------------------------


@dataclass
class Plan:
    """
    A unified plan wrapper.

    A plan may include:
    - A trajectory intent (e.g., waypoints/segments)
    - A schedule (events)
    - Arbitrary metadata for domain specifics

    For aircraft, you might fill `waypoints` + optional `segments`.
    For spacecraft, you might fill `schedule`.
    """

    kind: str  # "aircraft" or "spacecraft" (or other)
    waypoints: Optional[List[Dict[str, Any]]] = (
        None  # each dict can contain x/y/z, lat/lon/alt, eta, etc.
    )
    schedule: Optional[Schedule] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------
# Simulation output (unified "what happened")
# ---------------------------


@dataclass
class SimResult:
    """
    Unified simulation result container.

    Both domains can fill:
    - trajectory: time series state history (optional but recommended)
    - schedule: executed events (optional)
    - resources: time series of resource levels (battery, fuel, data storage, etc.)
    - scalars: summary values used by objectives/constraints (time, energy_used, mission_value)

    Constraints/Objectives should rely on these fields (and metadata) so they remain domain-agnostic.
    """

    t: np.ndarray  # shape (T,) time points for any time series fields
    trajectory: Optional[Trajectory] = None
    schedule: Optional[Schedule] = None

    # Resource traces (each should be shape (T,))
    resources: Dict[str, np.ndarray] = field(default_factory=dict)

    # Scalars for convenience (objective terms often read these)
    scalars: Dict[str, float] = field(default_factory=dict)

    # Rich domain-specific artifacts
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.t = np.array(self.t, dtype=float).reshape(-1)
        for k, v in list(self.resources.items()):
            arr = np.array(v, dtype=float).reshape(-1)
            if arr.shape[0] != self.t.shape[0]:
                raise ValueError(f"Resource '{k}' must have same length as t.")
            self.resources[k] = arr

    # Convenience accessors
    def resource(self, name: str) -> np.ndarray:
        return self.resources[name]

    def scalar(self, name: str, default: Optional[float] = None) -> float:
        if name in self.scalars:
            return float(self.scalars[name])
        if default is None:
            raise KeyError(f"Scalar '{name}' not present in SimResult.scalars")
        return float(default)
