# mission_framework/aircraft/model.py
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional

import numpy as np

from mission_framework.core.types import SimResult, Trajectory, Plan

# New modules (AeroHack-ready)
from mission_framework.aircraft.wind_model import WindModel, ZeroWind, StochasticWind
from mission_framework.aircraft.battery_model import BatteryModel, BatteryParams
from mission_framework.aircraft.dynamics import (
    AircraftKinematics,
    AircraftParams as DynParams,
    AircraftState,
    wrap_angle_rad,
)
from mission_framework.aircraft.geofence import GeofenceMap


@dataclass(frozen=True)
class AircraftSimParams:
    """
    High-level sim settings + guidance settings for a waypoint-following demo.
    We keep these separate from dynamics params so you can tune guidance without touching physics.
    """
    # simulation
    t_max_s: float = 10_000.0
    reach_radius_m: float = 15.0

    # stall detection (fail-fast if we can't make progress)
    stall_time_s: float = 120.0
    stall_improve_m: float = 1.0

    # guidance
    k_heading: float = 1.2            # heading error -> yaw rate command (through psi_cmd)
    k_speed: float = 0.8              # speed error -> accel proxy (we use v_air_cmd lag in dynamics)
    max_speed_step_mps: float = 3.0   # per-step clamp on v_air_cmd changes


@dataclass
class AircraftSim:
    """
    Aircraft simulator (point-mass + heading dynamics + wind + battery).

    Key AeroHack requirements covered:
    - Wind: injected via WindModel (time-varying/spatial/stochastic)
    - Maneuver: bank-angle -> yaw rate limit inside AircraftKinematics
    - Endurance: explicit BatteryModel integration
    - Geofence: optional GeofenceMap audit at the end (trajectory-level)
    """
    dyn: DynParams = DynParams()
    sim: AircraftSimParams = AircraftSimParams()

    wind: WindModel = ZeroWind()
    battery_params: BatteryParams = BatteryParams(capacity_Wh=800.0)

    geofence: Optional[GeofenceMap] = None
    geofence_clearance_m: float = 0.0  # buffer distance (0 = strict boundary)

    def simulate(
        self,
        plan: Plan,
        rng: Optional[np.random.Generator] = None,
        t_max_s: Optional[float] = None,
    ) -> SimResult:
        """
        Plan.waypoints must include at least START and one waypoint with x_m/y_m.
        We follow waypoints in order, with maneuver limits + wind + battery.
        """
        if not plan.waypoints or len(plan.waypoints) < 2:
            raise ValueError("Aircraft plan must include at least START and one waypoint.")

        rng = rng or np.random.default_rng()

        # If wind is stochastic, reset it per rollout for determinism with rng
        if isinstance(self.wind, StochasticWind):
            self.wind.reset(rng)

        kin = AircraftKinematics(self.dyn, wind=self.wind)
        batt = BatteryModel(self.battery_params)
        batt.reset()

        wps = plan.waypoints

        dt = float(self.dyn.dt_s)
        if dt <= 0:
            raise ValueError("Dynamics dt_s must be > 0")

        t_max = float(self.sim.t_max_s if t_max_s is None else t_max_s)

        # initial state
        x0 = float(wps[0].get("x_m", 0.0))
        y0 = float(wps[0].get("y_m", 0.0))
        z0 = float(wps[0].get("z_m", 0.0))

        psi0 = float(plan.metadata.get("heading_rad", 0.0))
        v0 = float(plan.metadata.get("speed_mps", (self.dyn.v_air_min_mps + self.dyn.v_air_max_mps) / 2.0))
        v0 = float(np.clip(v0, self.dyn.v_air_min_mps, self.dyn.v_air_max_mps))

        # battery initial from plan (optional)
        if "battery_Wh" in plan.metadata:
            batt.state.energy_Wh = float(np.clip(float(plan.metadata["battery_Wh"]), 0.0, self.battery_params.capacity_Wh))

        # commanded cruise speed from decisions/metadata
        v_cmd = float(plan.metadata.get("cruise_speed_mps", v0))
        v_cmd = float(np.clip(v_cmd, self.dyn.v_air_min_mps, self.dyn.v_air_max_mps))

        # logs
        t = 0.0
        idx = 1  # next waypoint index

        t_hist: List[float] = [t]
        state_hist: List[List[float]] = [[x0, y0, z0, psi0, v0, batt.state.energy_Wh]]
        wind_hist: List[List[float]] = [[0.0, 0.0, 0.0]]
        vground_hist: List[List[float]] = [[0.0, 0.0, 0.0]]
        yawrate_hist: List[float] = [0.0]
        reached_hist: List[float] = [0.0]

        # stall detection
        best_dist = float("inf")
        stall_steps = 0
        stall_limit = max(1, int(self.sim.stall_time_s / dt))

        s = AircraftState(x_m=x0, y_m=y0, z_m=z0, psi_rad=psi0, v_air_mps=v0)

        while t < t_max and idx < len(wps) and batt.state.energy_Wh > -1e-6:
            tx = float(wps[idx].get("x_m", 0.0))
            ty = float(wps[idx].get("y_m", 0.0))

            dx = tx - s.x_m
            dy = ty - s.y_m
            dist = math.hypot(dx, dy)

            # waypoint reached?
            if dist <= float(self.sim.reach_radius_m):
                idx += 1
                best_dist = float("inf")
                stall_steps = 0
                reached_hist[-1] = 1.0
                continue

            # stall detection
            if dist < best_dist - float(self.sim.stall_improve_m):
                best_dist = dist
                stall_steps = 0
            else:
                stall_steps += 1
                if stall_steps > stall_limit:
                    break

            # desired heading to waypoint
            psi_des = math.atan2(dy, dx)
            e = wrap_angle_rad(psi_des - s.psi_rad)

            # convert heading error into a psi_cmd one step ahead (bounded)
            # (kinematics will enforce yaw-rate/bank constraints)
            psi_cmd = wrap_angle_rad(s.psi_rad + self.sim.k_heading * e)

            # speed command with small per-step changes (stability)
            # dynamics uses 1st-order lag to reach v_air_cmd
            v_err = v_cmd - s.v_air_mps
            v_air_cmd = s.v_air_mps + float(np.clip(self.sim.k_speed * v_err, -self.sim.max_speed_step_mps, self.sim.max_speed_step_mps))
            v_air_cmd = float(np.clip(v_air_cmd, self.dyn.v_air_min_mps, self.dyn.v_air_max_mps))

            # step dynamics
            step = kin.step(
                s=s,
                t_s=t,
                psi_cmd_rad=psi_cmd,
                yaw_rate_cmd_radps=None,
                vz_cmd_mps=0.0,
                v_air_cmd_mps=v_air_cmd,
            )
            s = step.state

            # battery drain uses *air-relative* speed and yaw rate proxy
            batt.step(
                dt_s=dt,
                v_air_mps=float(np.linalg.norm(step.v_air_enu_mps[:2])),
                climb_rate_mps=step.climb_rate_mps,
                yaw_rate_radps=step.yaw_rate_radps,
            )

            # log
            t += dt
            t_hist.append(t)
            state_hist.append([s.x_m, s.y_m, s.z_m, s.psi_rad, s.v_air_mps, batt.state.energy_Wh])
            wind_hist.append([float(step.wind_enu_mps[0]), float(step.wind_enu_mps[1]), float(step.wind_enu_mps[2])])
            vground_hist.append([float(step.v_ground_enu_mps[0]), float(step.v_ground_enu_mps[1]), float(step.v_ground_enu_mps[2])])
            yawrate_hist.append(float(step.yaw_rate_radps))
            reached_hist.append(0.0)

        t_arr = np.array(t_hist, dtype=float)
        state_arr = np.array(state_hist, dtype=float)
        wind_arr = np.array(wind_hist, dtype=float)
        vground_arr = np.array(vground_hist, dtype=float)
        yawrate_arr = np.array(yawrate_hist, dtype=float)

        traj = Trajectory(
            t=t_arr,
            state=state_arr,
            control=None,
            frame="ENU",
            metadata={
                "state_order": ["x_m", "y_m", "z_m", "heading_rad", "v_air_mps", "battery_Wh"],
            },
        )

        battery_trace = state_arr[:, 5]
        t_end = float(t_arr[-1])
        energy_used_Wh = float(max(0.0, battery_trace[0] - battery_trace[-1]))

        # --- geofence audit (trajectory-level) ---
        nfz_viol = 0.0
        min_clear = float("inf")
        geofence_audit_payload: Optional[Dict[str, Any]] = None
        if self.geofence is not None:
            audit = self.geofence.audit_trajectory(
                xs_m=state_arr[:, 0].tolist(),
                ys_m=state_arr[:, 1].tolist(),
                clearance_m=float(self.geofence_clearance_m),
            )
            nfz_viol = 1.0 if audit.violated else 0.0
            min_clear = float(audit.min_clearance_m)
            geofence_audit_payload = {
                "violated": audit.violated,
                "min_clearance_m": audit.min_clearance_m,
                "min_clearance_index": audit.min_clearance_index,
                "min_clearance_point": audit.min_clearance_point,
                "num_hits": len(audit.hits),
                "hits": [
                    {"zone_id": h.zone_id, "index": h.index, "point": h.point, "kind": h.kind}
                    for h in audit.hits[:50]  # keep bounded
                ],
                "metadata": audit.metadata,
            }

        # Scalars for objectives/constraints
        sim = SimResult(
            t=t_arr,
            trajectory=traj,
            resources={
                "battery_Wh": battery_trace,
                "energy_used_Wh": np.array([energy_used_Wh], dtype=float),
                "wind_enu_mps": wind_arr,
                "v_ground_enu_mps": vground_arr,
                "yaw_rate_radps": yawrate_arr,
                "geofence_violated": np.array([nfz_viol], dtype=float),
                "geofence_min_clearance_m": np.array([min_clear], dtype=float),
                "waypoint_reached_flag": np.array(reached_hist, dtype=float),
            },
            scalars={
                "t_end_s": t_end,
                "energy_used_Wh": energy_used_Wh,
                "final_battery_Wh": float(battery_trace[-1]),
                "waypoints_completed": float(min(idx, len(wps) - 1)),
                "waypoints_total": float(len(wps) - 1),
                "geofence_violated": float(nfz_viol),
                "geofence_min_clearance_m": float(min_clear),
            },
            metadata={
                "reached_all": bool(idx >= len(wps)),
                "geofence_audit": geofence_audit_payload,
            },
        )
        return sim