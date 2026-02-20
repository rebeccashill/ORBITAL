# mission_framework/simulation/metrics.py
"""
Performance metrics for mission simulations.

This module extracts performance metrics from a completed simulation.
It does NOT define constraints or objectives — it only measures outcomes.

Metrics categories:
- Time    → mission duration
- Energy  → fuel / delta-v / power usage
- Value   → science return, coverage, revenue proxies
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

# ============================================================
# Dataclasses
# ============================================================


@dataclass(frozen=True)
class TimeMetrics:
    duration: float
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "duration": float(self.duration),
            "start_time": float(self.start_time),
            "end_time": float(self.end_time),
        }


@dataclass(frozen=True)
class EnergyMetrics:
    fuel_used: float
    fuel_remaining: float
    delta_v_used: Optional[float] = None
    power_used: Optional[float] = None

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "fuel_used": float(self.fuel_used),
            "fuel_remaining": float(self.fuel_remaining),
            "delta_v_used": None if self.delta_v_used is None else float(self.delta_v_used),
            "power_used": None if self.power_used is None else float(self.power_used),
        }


@dataclass(frozen=True)
class ValueMetrics:
    science_value: Optional[float] = None
    revenue_value: Optional[float] = None
    coverage_score: Optional[float] = None

    def total(self) -> float:
        total = 0.0
        for v in (self.science_value, self.revenue_value, self.coverage_score):
            if v is not None:
                total += float(v)
        return total

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "science_value": None if self.science_value is None else float(self.science_value),
            "revenue_value": None if self.revenue_value is None else float(self.revenue_value),
            "coverage_score": None if self.coverage_score is None else float(self.coverage_score),
            "total": self.total(),
        }
