# mission_framework/aircraft/wind.py
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Tuple, Optional
import numpy as np


@dataclass(frozen=True)
class WindField:
    """Interface: wind(t, x, y) -> (wx, wy) in m/s."""

    def wind(
        self, t_s: float, x_m: float, y_m: float, rng: Optional[np.random.Generator] = None
    ) -> Tuple[float, float]:
        raise NotImplementedError


@dataclass(frozen=True)
class SinusoidalWind(WindField):
    base_speed_mps: float = 5.0
    direction_rad: float = 0.0
    gust_amplitude_mps: float = 2.0
    gust_frequency_hz: float = 0.005
    spatial_wavelength_m: float = 5000.0  # mild spatial variation

    def wind(
        self, t_s: float, x_m: float, y_m: float, rng: Optional[np.random.Generator] = None
    ) -> Tuple[float, float]:
        # Base wind
        bx = self.base_speed_mps * math.cos(self.direction_rad)
        by = self.base_speed_mps * math.sin(self.direction_rad)

        # Time gust
        gust_t = self.gust_amplitude_mps * math.sin(2.0 * math.pi * self.gust_frequency_hz * t_s)

        # Spatial ripple (very mild, keeps it realistic)
        phase = 2.0 * math.pi * ((x_m + 0.7 * y_m) / max(1.0, self.spatial_wavelength_m))
        gust_s = 0.5 * self.gust_amplitude_mps * math.sin(phase)

        g = gust_t + gust_s
        # Add stochastic gust (per-case variation)
        if rng is not None:
            g += float(rng.normal(0.0, 0.5))  # 0.5 m/s std dev

        # Gust in direction perpendicular-ish to base for variety
        gx = g * math.cos(self.direction_rad + math.pi / 2.0)
        gy = g * math.sin(self.direction_rad + math.pi / 2.0)
        return (bx + gx, by + gy)


@dataclass(frozen=True)
class NoWind(WindField):
    def wind(
        self, t_s: float, x_m: float, y_m: float, rng: Optional[np.random.Generator] = None
    ) -> Tuple[float, float]:
        return (0.0, 0.0)
