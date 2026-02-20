# mission_framework/spacecraft/orbit.py
from __future__ import annotations

import math
from typing import Optional, Dict, Any, List, Tuple
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


def _parse_epoch_unix(epoch_utc: str) -> Optional[float]:
    """
    Parse an ISO 8601 UTC string to a Unix timestamp.
    Returns None if the string is empty or cannot be parsed.
    """
    if not epoch_utc:
        return None
    try:
        from datetime import datetime, timezone
        s = epoch_utc.rstrip("Z")
        fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in s else "%Y-%m-%dT%H:%M:%S"
        dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def keplerian_to_eci_state(el: KeplerianElements) -> np.ndarray:
    """
    Convert KeplerianElements to an initial ECI Cartesian state vector
    [rx, ry, rz, vx, vy, vz] in metres and m/s.
    """
    MU = 3.986004418e14  # m^3/s^2
    a = el.a_km * 1000.0
    e = el.e
    i = el.i_rad
    raan = el.raan_rad
    argp = el.argp_rad
    M0 = el.M0_rad

    # Solve Kepler's equation M = E - e*sin(E) via Newton-Raphson
    E = M0
    for _ in range(50):
        dE = (M0 - E + e * math.sin(E)) / (1.0 - e * math.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break

    nu = 2.0 * math.atan2(
        math.sqrt(1.0 + e) * math.sin(E / 2.0),
        math.sqrt(1.0 - e) * math.cos(E / 2.0),
    )

    p = a * (1.0 - e * e)
    r = p / (1.0 + e * math.cos(nu))

    r_pf = np.array([r * math.cos(nu), r * math.sin(nu), 0.0], dtype=float)
    v_pf = np.array([
        -math.sqrt(MU / p) * math.sin(nu),
        math.sqrt(MU / p) * (e + math.cos(nu)),
        0.0,
    ], dtype=float)

    # Rotation from perifocal to ECI (Rz(-raan) · Rx(-i) · Rz(-argp))
    co, so = math.cos(argp), math.sin(argp)
    ci, si = math.cos(i), math.sin(i)
    cr, sr = math.cos(raan), math.sin(raan)

    Q = np.array([
        [cr*co - sr*so*ci, -cr*so - sr*co*ci,  sr*si],
        [sr*co + cr*so*ci, -sr*so + cr*co*ci, -cr*si],
        [so*si,             co*si,              ci   ],
    ], dtype=float)

    return np.hstack([Q @ r_pf, Q @ v_pf])


def propagate_ecef_trajectory(
    el: KeplerianElements,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Propagate *el* from its epoch and return (t_rel, r_ecef).

    t_rel : 1-D array of seconds relative to epoch, shape (N,)
    r_ecef: satellite ECEF positions in metres, shape (N, 3)
    """
    epoch_unix = _parse_epoch_unix(el.epoch_utc)
    if epoch_unix is None:
        epoch_unix = 0.0
    n = max(1, int(math.floor((t_end_s - t_start_s) / dt_s)) + 1)
    t_rel = t_start_s + dt_s * np.arange(n, dtype=float)
    n = t_rel.shape[0]

    x = keplerian_to_eci_state(el)
    r_ecef_arr = np.zeros((n, 3), dtype=float)

    for k in range(n):
        jd = julian_date_from_unix(epoch_unix + float(t_rel[k]))
        re, _ = eci_to_ecef(x[:3], x[3:], jd)
        r_ecef_arr[k] = re
        if k < n - 1:
            x = rk4_step(dynamics_eci, x, float(dt_s))

    return t_rel, r_ecef_arr


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