# mission_framework/aircraft/model.py
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional

import numpy as np

from mission_framework.core.types import SimResult, Trajectory, Plan
from mission_framework.aircraft.wind import WindField, NoWind
from mission_framework.aircraft.energy import EnergyModel
from mission_framework.aircraft.geofence import GeofenceMap


def wrap_pi(a: float) -> float:
    """Wrap angle to [-pi, pi]."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


@dataclass(frozen=True)
class AircraftParams:
    # speed/turn limits
    min_speed_mps: float = 12.0
    max_speed_mps: float = 30.0
    max_turn_rate_radps: float = 0.35
    # battery
    battery_capacity_Wh: float = 800.0
    # simulation
    dt_s: float = 5.0
    reach_radius_m: float = 15.0
    # stall detection
    stall_time_s: float = 120.0          # how long we tolerate no progress
    stall_improve_m: float = 1.0         # improvement threshold to reset stall


@dataclass
class AircraftSim:
    params: AircraftParams
    wind: WindField = NoWind()
    energy: EnergyModel = EnergyModel()
    geofence: Optional[GeofenceMap] = None

    # Simple guidance tuning
    k_heading: float = 1.2  # heading error -> turn rate
    k_speed: float = 0.8    # speed error -> accel (m/s^2)
    max_accel_mps2: float = 2.0

    def simulate(
        self,
        plan: Plan,
        rng: Optional[np.random.Generator] = None,
        t_max_s: float = 10_000.0,
    ) -> SimResult:
        """
        Plan.waypoints must include at least START and one waypoint with x_m/y_m.
        We follow waypoints in order, with turn-rate limits and wind.
        """
        if not plan.waypoints or len(plan.waypoints) < 2:
            raise ValueError("Aircraft plan must include at least START and one waypoint.")

        wps = plan.waypoints

        # Fixed timestep (set once!)
        dt = float(self.params.dt_s)
        if dt <= 0:
            raise ValueError("AircraftParams.dt_s must be > 0")

        # initial
        x = float(wps[0].get("x_m", 0.0))
        y = float(wps[0].get("y_m", 0.0))
        psi = float(plan.metadata.get("heading_rad", 0.0))
        v = float(plan.metadata.get("speed_mps", (self.params.min_speed_mps + self.params.max_speed_mps) / 2.0))
        v = float(np.clip(v, self.params.min_speed_mps, self.params.max_speed_mps))

        batt = float(plan.metadata.get("battery_Wh", self.params.battery_capacity_Wh))
        batt = float(np.clip(batt, 0.0, self.params.battery_capacity_Wh))

        # commanded speed (from decisions)
        v_cmd = float(plan.metadata.get("cruise_speed_mps", v))
        v_cmd = float(np.clip(v_cmd, self.params.min_speed_mps, self.params.max_speed_mps))

        # tracking
        t = 0.0
        idx = 1  # next waypoint index

        t_hist: List[float] = [t]
        state_hist: List[List[float]] = [[x, y, psi, v, batt]]
        windx_hist: List[float] = [0.0]
        windy_hist: List[float] = [0.0]
        inside_nf_hist: List[float] = [0.0]

        # stall detection variables (persist across loop)
        best_dist = float("inf")
        stall_steps = 0
        stall_limit = max(1, int(self.params.stall_time_s / dt))

        # simulate until last waypoint reached or timeout or battery dead
        while t < t_max_s and idx < len(wps) and batt > -1e-6:
            tx = float(wps[idx]["x_m"])
            ty = float(wps[idx]["y_m"])

            dx = tx - x
            dy = ty - y
            dist = math.hypot(dx, dy)

            # waypoint reached?
            if dist <= float(self.params.reach_radius_m):
                idx += 1
                best_dist = float("inf")
                stall_steps = 0
                continue

            # stall detection (no progress toward current waypoint)
            if dist < best_dist - float(self.params.stall_improve_m):
                best_dist = dist
                stall_steps = 0
            else:
                stall_steps += 1
                if stall_steps > stall_limit:
                    # Give up on this rollout; planner will penalize via constraints (not all waypoints completed).
                    break

            # desired heading to waypoint
            psi_des = math.atan2(dy, dx)
            e = wrap_pi(psi_des - psi)

            # turn rate command (limited)
            turn_rate_cmd = self.k_heading * e
            turn_rate = float(
                np.clip(turn_rate_cmd, -self.params.max_turn_rate_radps, self.params.max_turn_rate_radps)
            )

            # speed control (simple accel clamp)
            a_cmd = self.k_speed * (v_cmd - v)
            a = float(np.clip(a_cmd, -self.max_accel_mps2, self.max_accel_mps2))

            # wind at current state/time
            wx, wy = self.wind.wind(t, x, y, rng=rng)

            # update heading and speed
            psi = wrap_pi(psi + turn_rate * dt)
            v = float(np.clip(v + a * dt, self.params.min_speed_mps, self.params.max_speed_mps))

            # air-relative velocity
            vx_air = v * math.cos(psi)
            vy_air = v * math.sin(psi)

            # ground velocity
            vx = vx_air + wx
            vy = vy_air + wy

            # integrate position
            x += vx * dt
            y += vy * dt

            # energy drain
            batt -= self.energy.drain_Wh(v_mps=v, turn_rate_radps=turn_rate, dt_s=dt)

            # geofence flag
            inside = 1.0 if (self.geofence is not None and self.geofence.is_violation(x, y)) else 0.0

            # log
            t += dt
            t_hist.append(t)
            state_hist.append([x, y, psi, v, batt])
            windx_hist.append(wx)
            windy_hist.append(wy)
            inside_nf_hist.append(inside)

        t_arr = np.array(t_hist, dtype=float)
        state_arr = np.array(state_hist, dtype=float)

        traj = Trajectory(
            t=t_arr,
            state=state_arr,
            control=None,
            frame="ENU",
            metadata={"state_order": ["x_m", "y_m", "heading_rad", "speed_mps", "battery_Wh"]},
        )

        # resources & scalars
        battery_trace = state_arr[:, 4]
        t_end = float(t_arr[-1])
        energy_used = float(max(0.0, battery_trace[0] - battery_trace[-1]))

        sim = SimResult(
            t=t_arr,
            trajectory=traj,
            resources={
                "battery_Wh": battery_trace,
                "wind_x_mps": np.array(windx_hist, dtype=float),
                "wind_y_mps": np.array(windy_hist, dtype=float),
                "nfz_inside": np.array(inside_nf_hist, dtype=float),
            },
            scalars={
                "t_end_s": t_end,
                "energy_used_Wh": energy_used,
                "final_battery_Wh": float(battery_trace[-1]),
                "waypoints_completed": float(min(idx, len(wps) - 1)),
                "waypoints_total": float(len(wps) - 1),
            },
            metadata={"reached_all": bool(idx >= len(wps))},
        )
        return sim