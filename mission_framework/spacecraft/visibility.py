# mission_framework/spacecraft/visibility.py
from __future__ import annotations
import numpy as np

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np

R_EARTH = 6378137.0  # m

# -------------------------
# Existing helpers (keep yours)
# -------------------------

def geodetic_to_ecef(lat_rad: float, lon_rad: float, alt_m: float) -> np.ndarray:
    clat, slat = np.cos(lat_rad), np.sin(lat_rad)
    clon, slon = np.cos(lon_rad), np.sin(lon_rad)
    r = R_EARTH + float(alt_m)
    return np.array([r * clat * clon, r * clat * slon, r * slat], dtype=float)

def elevation_angle_rad(r_sat_ecef: np.ndarray, r_gs_ecef: np.ndarray) -> float:
    rho = r_sat_ecef - r_gs_ecef
    rho_hat = rho / np.linalg.norm(rho)
    zenith_hat = r_gs_ecef / np.linalg.norm(r_gs_ecef)
    return float(np.arcsin(np.clip(np.dot(rho_hat, zenith_hat), -1.0, 1.0)))

def ecef_to_latlon(r_ecef: np.ndarray):
    x, y, z = float(r_ecef[0]), float(r_ecef[1]), float(r_ecef[2])
    lon = np.arctan2(y, x)
    hyp = np.sqrt(x*x + y*y)
    lat = np.arctan2(z, hyp)
    return float(lat), float(lon)

# -------------------------
# Compatibility layer for mission.py
# -------------------------

@dataclass(frozen=True)
class GroundSite:
    """
    Compatibility GroundSite that can be constructed even if mission.py omits 'name'.
    """
    # Make name optional/defaultable
    name: str = ""
    lat_deg: float = 0.0
    lon_deg: float = 0.0

    alt_m: float = 0.0
    alt_km: Optional[float] = None
    min_elev_deg: float = 10.0
    site_id: Optional[str] = None

    def __post_init__(self):
        # Convert alt_km -> alt_m if provided
        if self.alt_km is not None:
            object.__setattr__(self, "alt_m", float(self.alt_km) * 1000.0)

        # If no name was provided, use site_id or a generic label
        if (self.name is None) or (str(self.name).strip() == ""):
            fallback = self.site_id if self.site_id else "GS"
            object.__setattr__(self, "name", str(fallback))

    def ecef(self) -> np.ndarray:
        return geodetic_to_ecef(
            np.deg2rad(self.lat_deg),
            np.deg2rad(self.lon_deg),
            self.alt_m,
        )

    @property
    def min_elev_rad(self) -> float:
        return float(np.deg2rad(self.min_elev_deg))

from typing import Dict, List, Tuple, Optional
import numpy as np

from typing import Dict, List, Tuple, Optional, Any
import numpy as np

def compute_access_windows(*args, **kwargs) -> Dict[str, List[Tuple[float, float]]]:
    """
    Ultra-compatible access window function.

    Supports:
      - mission.py style: compute_access_windows(<something>, <something>, t_start_s=..., step_s=..., cfg=..., ...)
      - direct style: compute_access_windows(t=<array>, r_ecef=<T,3>, sites=[...])

    We accept positional args because mission.py is passing them.
    """
    # -------------------------
    # Pull common kwargs (with aliases)
    # -------------------------
    t = kwargs.pop("t", None)
    r_ecef = kwargs.pop("r_ecef", None)
    sites = kwargs.pop("sites", None)

    t_start_s = kwargs.pop("t_start_s", None)
    t_end_s   = kwargs.pop("t_end_s", None)

    dt_s   = kwargs.pop("dt_s", None)
    step_s = kwargs.pop("step_s", None)
    if dt_s is None and step_s is not None:
        dt_s = step_s

    # accepted but optional/ignored by the math right now
    _cfg = kwargs.pop("cfg", None)
    min_elevation_deg = kwargs.pop("min_elevation_deg", None)

    # If mission.py passed extra stuff, ignore it safely
    # (prevents future whack-a-mole)
    # kwargs now contains only truly unknown extras
    # -------------------------

    # -------------------------
    # Handle positional arguments (mission.py is doing this)
    # Common patterns:
    #   compute_access_windows(sites, r_ecef, t_start_s=..., ...)
    #   compute_access_windows(r_ecef, sites, t_start_s=..., ...)
    #   compute_access_windows(r_ecef, wins_cfg, ..., sites=...)
    # We’ll try to infer:
    #   - r_ecef: first array-like with shape (T,3)
    #   - sites: first list-like of GroundSite
    # -------------------------
    if args:
        for a in args:
            # infer r_ecef
            if r_ecef is None:
                try:
                    arr = np.array(a, dtype=float)
                    if arr.ndim == 2 and arr.shape[1] == 3:
                        r_ecef = arr
                        continue
                except Exception:
                    pass

            # infer sites
            if sites is None and isinstance(a, list):
                sites = a
                continue

        # If after inference we still don't have sites, but one arg is a dict with 'sites'
        if sites is None:
            for a in args:
                if isinstance(a, dict) and "sites" in a:
                    sites = a["sites"]

    if sites is None:
        sites = []

    # Apply global minimum elevation if provided and a site lacks a min_elev_deg
    if min_elevation_deg is not None:
        new_sites = []
        for s in sites:
            # If site has attribute min_elev_deg already, keep it
            if getattr(s, "min_elev_deg", None) is None:
                # rebuild with a default
                new_sites.append(
                    GroundSite(
                        name=getattr(s, "name", "") or getattr(s, "site_id", None) or "GS",
                        lat_deg=float(getattr(s, "lat_deg", 0.0)),
                        lon_deg=float(getattr(s, "lon_deg", 0.0)),
                        alt_m=float(getattr(s, "alt_m", 0.0)),
                        alt_km=getattr(s, "alt_km", None),
                        min_elev_deg=float(min_elevation_deg),
                        site_id=getattr(s, "site_id", None),
                    )
                )
            else:
                new_sites.append(s)
        sites = new_sites

    # -------------------------
    # Build time grid if not given
    # -------------------------
    if t is None:
        if t_start_s is None or t_end_s is None or dt_s is None:
            raise TypeError(
                "compute_access_windows needs either (t, r_ecef) or (t_start_s, t_end_s, dt/step, r_ecef). "
                "Got positional args + kwargs that did not include enough info."
            )
        t = np.arange(float(t_start_s), float(t_end_s) + 1e-9, float(dt_s), dtype=float)
    else:
        t = np.array(t, dtype=float).reshape(-1)

    if r_ecef is None:
        raise TypeError("compute_access_windows: r_ecef is required (either positional or keyword).")

    r_ecef = np.array(r_ecef, dtype=float)
    if r_ecef.ndim != 2 or r_ecef.shape[1] != 3:
        raise ValueError("r_ecef must be shape (T,3).")
    if r_ecef.shape[0] != t.shape[0]:
        raise ValueError("r_ecef must have same length as t.")

    # -------------------------
    # Compute access windows
    # -------------------------
    out: Dict[str, List[Tuple[float, float]]] = {}

    for site in sites:
        name = getattr(site, "name", "") or getattr(site, "site_id", None) or "GS"
        r_gs = site.ecef()
        min_el = site.min_elev_rad

        mask = np.zeros(t.shape[0], dtype=bool)
        for k in range(t.shape[0]):
            el = elevation_angle_rad(r_ecef[k], r_gs)
            mask[k] = (el >= min_el)

        windows: List[Tuple[float, float]] = []
        in_win = False
        t0 = 0.0

        for k in range(t.shape[0]):
            if mask[k] and not in_win:
                in_win = True
                t0 = float(t[k])
            if in_win and (not mask[k]):
                t1 = float(t[k])
                if t1 > t0:
                    windows.append((t0, t1))
                in_win = False

        if in_win:
            t1 = float(t[-1])
            if t1 > t0:
                windows.append((t0, t1))

        out[str(name)] = windows

    return out

R_EARTH = 6378137.0  # m