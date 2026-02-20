# mission_framework/spacecraft/orbit.py
from __future__ import annotations

from typing import Optional, Dict, Any, List, Any
import numpy as np

from mission_framework.core.types import SimResult, Plan

from mission_framework.spacecraft.frames import julian_date_from_unix, eci_to_ecef
from mission_framework.spacecraft.dynamics import rk4_step, dynamics_eci
from mission_framework.spacecraft.visibility import (
    geodetic_to_ecef,
    elevation_angle_rad,
    ecef_to_latlon,
)

from dataclasses import dataclass

# Keep this constant for backward compatibility with mission.py
R_EARTH_KM = 6378.137

@dataclass(frozen=True)
class KeplerianElements:
    """
    Compatibility container for mission.py YAML parsing.

    mission.py may pass:
      a_km, e, i_rad, raan_rad, argp_rad,
      nu_rad, M0_rad,
      epoch_utc (string like '2026-02-01T00:00:00Z' or similar)

    Your simulator can ignore fields it doesn't use.
    """
    a_km: float
    e: float
    i_rad: float
    raan_rad: float
    argp_rad: float

    # optional anomalies
    nu_rad: float = 0.0
    M0_rad: float = 0.0

    # optional epoch string from YAML
    epoch_utc: str = ""

@dataclass
class OrbitConfig:
    """
    Compatibility config object for mission.py.

    mission.py constructs OrbitConfig() then populates fields.
    So everything must have defaults.
    """
    elements: Optional[KeplerianElements] = None
    dt_s: float = 10.0
    j2: bool = True

    # optional knobs mission.py might set
    drag: bool = False
    area_m2: float = 0.0
    cd: float = 2.2
    mass_kg: float = 0.0

def simulate(plan: Plan, rng: Optional[np.random.Generator]) -> SimResult:
    """
    Spacecraft domain simulation:
    - propagate in ECI with two-body + J2 (RK4)
    - each step compute JD and transform to ECEF for:
        * ground station elevation
        * ground track / KML outputs
        * visibility booleans/windows
    """
    # -------------------------
    # Pull inputs (rename as needed)
    # -------------------------
    t0 = float(getattr(plan, "t0_unix_s", getattr(plan, "epoch_unix_s", 0.0)))
    horizon_s = float(getattr(plan, "horizon_s", getattr(plan, "duration_s", 7 * 86400.0)))
    dt = float(getattr(plan, "dt_s", 10.0))

    x0 = np.array(getattr(plan, "x0_eci", getattr(plan, "initial_state_eci")), dtype=float).reshape(6)

    ground_stations = getattr(plan, "ground_stations", [])
    # Precompute ground station ECEF + min elev
    gs_cache = []
    for gs in ground_stations:
        lat = np.deg2rad(float(gs["lat_deg"]))
        lon = np.deg2rad(float(gs["lon_deg"]))
        alt = float(gs.get("alt_m", 0.0))
        r_gs = geodetic_to_ecef(lat, lon, alt)
        min_el = np.deg2rad(float(gs.get("min_elev_deg", 10.0)))
        gs_cache.append((gs.get("name", "GS"), r_gs, min_el))

    # -------------------------
    # Time grid
    # -------------------------
    n = int(np.floor(horizon_s / dt)) + 1
    t = t0 + dt * np.arange(n, dtype=float)

    # -------------------------
    # Allocate outputs
    # -------------------------
    r_eci = np.zeros((n, 3), dtype=float)
    v_eci = np.zeros((n, 3), dtype=float)
    r_ecef = np.zeros((n, 3), dtype=float)
    v_ecef = np.zeros((n, 3), dtype=float)
    lat = np.zeros(n, dtype=float)
    lon = np.zeros(n, dtype=float)

    # visibility[name] = boolean array over time
    visibility: Dict[str, np.ndarray] = {name: np.zeros(n, dtype=bool) for (name, _, _) in gs_cache}
    max_elev: Dict[str, np.ndarray] = {name: np.full(n, -np.inf, dtype=float) for (name, _, _) in gs_cache}

    # Resources (keep simple placeholders; your constraints/objective likely populate these already)
    battery = np.zeros(n, dtype=float)
    data = np.zeros(n, dtype=float)

    # -------------------------
    # Main loop (propagate ECI, then transform for ops)
    # -------------------------
    x = x0.copy()
    for k in range(n):
        r_eci[k] = x[:3]
        v_eci[k] = x[3:]

        jd = julian_date_from_unix(t[k])
        re, ve = eci_to_ecef(r_eci[k], v_eci[k], jd)
        r_ecef[k] = re
        v_ecef[k] = ve

        la, lo = ecef_to_latlon(re)
        lat[k] = la
        lon[k] = lo

        # Ground station elevation checks in ECEF
        for (name, r_gs, min_el) in gs_cache:
            el = elevation_angle_rad(re, r_gs)
            max_elev[name][k] = el
            visibility[name][k] = (el >= min_el)

        # Example placeholder resource propagation (replace with your real power/data model)
        # Keeping deterministic:
        if k == 0:
            battery[k] = float(getattr(plan, "battery0", 1.0))
            data[k] = float(getattr(plan, "data0", 0.0))
        else:
            battery[k] = battery[k-1]
            data[k] = data[k-1]

        # Step dynamics (skip after last sample)
        if k < n - 1:
            x = rk4_step(dynamics_eci, x, dt)

    # -------------------------
    # Package SimResult (match your core.types)
    # -------------------------
    # If your Trajectory type exists, use it. If not, keep trajectory=None and stash arrays in scalars/extras.
    traj = None
    try:
        from mission_framework.core.types import Trajectory

        # pack ECI into a single state history: [rx, ry, rz, vx, vy, vz]
        state_hist = np.hstack([r_eci, v_eci])  # shape (N, 6)

        traj = Trajectory(
            t=t,
            state=state_hist,
        )
    except Exception:
        traj = None

    resources = {
        "battery": battery,
        "data_stored": data,
        # If you want constraints to read these easily, also expose contact booleans per station:
        **{f"contact_{name}": visibility[name].astype(float) for name in visibility.keys()},
    }

    scalars: Dict[str, Any] = {
        "dt_s": dt,
        "steps": n,
        "num_ground_stations": len(gs_cache),
    }

    return SimResult(
        t=t,
        resources=resources,
        scalars=scalars,
        trajectory=traj,
    )