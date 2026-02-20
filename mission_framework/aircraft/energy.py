# mission_framework/aircraft/energy.py
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EnergyModel:
    """
    Simple but credible power model:
      P = P_base + k_v * v^3 + k_turn * |turn_rate| * v
    """

    p_base_W: float = 250.0
    k_v: float = 0.03  # scales with v^3 (drag-ish)
    k_turn: float = 80.0  # extra power in turns

    def power_W(self, v_mps: float, turn_rate_radps: float) -> float:
        v = max(0.0, float(v_mps))
        w = abs(float(turn_rate_radps))
        return self.p_base_W + self.k_v * (v**3) + self.k_turn * w * v

    def drain_Wh(self, v_mps: float, turn_rate_radps: float, dt_s: float) -> float:
        P = self.power_W(v_mps, turn_rate_radps)
        return P * float(dt_s) / 3600.0
