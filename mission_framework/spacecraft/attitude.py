# mission_framework/spacecraft/attitude.py
"""
Attitude / pointing feasibility (MODULE B / spacecraft).

Goal:
- Provide a simplified slew-rate model suitable for 7-day scheduling.
- Check if a sequence of pointing tasks is feasible with limited angular rate.

We use a minimal abstraction:
- Each task has a "boresight direction" represented by a unit vector in ECEF (or any consistent frame).
- Slew time between two directions is angle / max_slew_rate.

For scheduling:
- A transition is feasible if:
    previous_task.end_time + slew_time <= next_task.start_time
- Optionally enforce a settle time after slews.

This model is intentionally simplified:
- No reaction wheel momentum saturation
- No detailed quaternion dynamics
- Good enough for hackathon planning and constraints

Units:
- Slew rate in deg/s or rad/s (internally we use rad/s)
- Vectors are 3D numpy arrays
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import math
import numpy as np


def unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float).reshape(3)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("Direction vector has near-zero magnitude.")
    return v / n


def angle_between_rad(a: np.ndarray, b: np.ndarray) -> float:
    """Angle between two direction vectors (radians)."""
    ua = unit(a)
    ub = unit(b)
    c = float(np.clip(np.dot(ua, ub), -1.0, 1.0))
    return float(math.acos(c))


@dataclass(frozen=True)
class SlewConfig:
    """
    Simplified slew model config.
    """

    max_slew_rate_deg_s: float = 2.0
    settle_time_s: float = 2.0  # time after a slew before task can start

    @property
    def max_slew_rate_rad_s(self) -> float:
        return math.radians(float(self.max_slew_rate_deg_s))


@dataclass(frozen=True)
class PointingTask:
    """
    A pointing task the scheduler cares about.

    direction_ecef: a 3D direction vector to point the boresight (unit not required)
    """

    t_start: float
    t_end: float
    direction_ecef: np.ndarray
    label: str = ""
    metadata: Optional[Dict[str, Any]] = None  # optional

    def __post_init__(self) -> None:
        # dataclass frozen: use object.__setattr__
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    @property
    def duration_s(self) -> float:
        return float(self.t_end - self.t_start)


def slew_time_s(dir_from: np.ndarray, dir_to: np.ndarray, cfg: SlewConfig = SlewConfig()) -> float:
    """Compute slew time (seconds) between two directions."""
    ang = angle_between_rad(dir_from, dir_to)
    w = float(cfg.max_slew_rate_rad_s)
    if w <= 0:
        return float("inf")
    return float(ang / w)


def transition_feasible(
    prev: PointingTask,
    nxt: PointingTask,
    *,
    cfg: SlewConfig = SlewConfig(),
) -> Tuple[bool, float]:
    """
    Check if prev -> nxt is feasible.

    Returns:
      (ok, required_gap_s)
    where required_gap_s = slew_time + settle_time.
    """
    req = slew_time_s(prev.direction_ecef, nxt.direction_ecef, cfg=cfg) + float(cfg.settle_time_s)
    gap = float(nxt.t_start - prev.t_end)
    return (gap >= req), float(req)


def sequence_feasibility_margin(
    tasks: Sequence[PointingTask],
    *,
    cfg: SlewConfig = SlewConfig(),
) -> float:
    """
    Returns the minimum (gap - required) margin across consecutive tasks.
    Positive => feasible with slack. Negative => infeasible.
    """
    if len(tasks) < 2:
        return float("inf")

    min_margin = float("inf")
    for a, b in zip(tasks[:-1], tasks[1:]):
        ok, req = transition_feasible(a, b, cfg=cfg)
        margin = float((b.t_start - a.t_end) - req)
        min_margin = min(min_margin, margin)
    return float(min_margin)
