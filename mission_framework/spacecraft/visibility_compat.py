# mission_framework/spacecraft/visibility_compat.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from .visibility_core import GroundSite, compute_access_windows as compute_access_windows_core


def compute_access_windows(*args: Any, **kwargs: Any) -> Dict[str, List[Tuple[float, float]]]:
    """
    Compatibility wrapper around visibility_core.compute_access_windows.

    Supports:
      - strict: compute_access_windows(t=..., r_ecef=..., sites=[...])
      - legacy: positional args + aliases like step_s, dt_s, min_elevation_deg, cfg, etc.

    Goal: normalize inputs and call the strict core API.
    """
    # pull known kwargs
    t = kwargs.pop("t", None)
    r_ecef = kwargs.pop("r_ecef", None)
    sites = kwargs.pop("sites", None)

    t_start_s = kwargs.pop("t_start_s", None)
    t_end_s = kwargs.pop("t_end_s", None)
    dt_s = kwargs.pop("dt_s", None)
    step_s = kwargs.pop("step_s", None)
    if dt_s is None and step_s is not None:
        dt_s = step_s

    min_elevation_deg = kwargs.pop("min_elevation_deg", None)

    # accepted but ignored
    kwargs.pop("cfg", None)

    # infer from positional args if needed
    if args:
        for a in args:
            if r_ecef is None:
                try:
                    arr = np.asarray(a, dtype=float)
                    if arr.ndim == 2 and arr.shape[1] == 3:
                        r_ecef = arr
                        continue
                except Exception:
                    pass
            if sites is None and isinstance(a, list):
                sites = a

    if sites is None:
        sites = []

    # apply global min elevation if caller provided it
    if min_elevation_deg is not None:
        new_sites: List[GroundSite] = []
        for s in sites:
            # If it's already a GroundSite, clone with updated min elev
            if isinstance(s, GroundSite):
                new_sites.append(
                    GroundSite(
                        name=s.name,
                        lat_deg=s.lat_deg,
                        lon_deg=s.lon_deg,
                        alt_m=s.alt_m,
                        min_elev_deg=float(min_elevation_deg),
                        site_id=s.site_id,
                    )
                )
            else:
                # best-effort for dict-like / older objects
                sid = getattr(s, "site_id", None) if not isinstance(s, dict) else s.get("site_id")
                name = getattr(s, "name", "") if not isinstance(s, dict) else s.get("name", "")
                lat = (
                    getattr(s, "lat_deg", 0.0) if not isinstance(s, dict) else s.get("lat_deg", 0.0)
                )
                lon = (
                    getattr(s, "lon_deg", 0.0) if not isinstance(s, dict) else s.get("lon_deg", 0.0)
                )
                alt_m = getattr(s, "alt_m", 0.0) if not isinstance(s, dict) else s.get("alt_m", 0.0)
                alt_km = (
                    getattr(s, "alt_km", None) if not isinstance(s, dict) else s.get("alt_km", None)
                )

                if alt_km is not None:
                    new_sites.append(
                        GroundSite.from_km(
                            site_id=sid,
                            lat_deg=float(lat),
                            lon_deg=float(lon),
                            alt_km=float(alt_km),
                            min_elev_deg=float(min_elevation_deg),
                            name=str(name or "") or str(sid or "GS"),
                        )
                    )
                else:
                    new_sites.append(
                        GroundSite(
                            name=str(name or "") or str(sid or "GS"),
                            lat_deg=float(lat),
                            lon_deg=float(lon),
                            alt_m=float(alt_m),
                            min_elev_deg=float(min_elevation_deg),
                            site_id=sid,
                        )
                    )
        sites = new_sites

    # normalize sites to core GroundSite
    core_sites: List[GroundSite] = []
    for s in sites:
        if isinstance(s, GroundSite):
            core_sites.append(s)
            continue

        # dict-like
        if isinstance(s, dict):
            sid = s.get("site_id")
            name = s.get("name", "") or (sid or "GS")
            lat = float(s.get("lat_deg", 0.0))
            lon = float(s.get("lon_deg", 0.0))
            if "alt_km" in s:
                core_sites.append(
                    GroundSite.from_km(
                        site_id=sid,
                        name=str(name),
                        lat_deg=lat,
                        lon_deg=lon,
                        alt_km=float(s.get("alt_km", 0.0)),
                        min_elev_deg=float(s.get("min_elev_deg", 10.0)),
                    )
                )
            else:
                core_sites.append(
                    GroundSite(
                        name=str(name),
                        lat_deg=lat,
                        lon_deg=lon,
                        alt_m=float(s.get("alt_m", 0.0)),
                        min_elev_deg=float(s.get("min_elev_deg", 10.0)),
                        site_id=sid,
                    )
                )
            continue

        # object with attributes
        sid = getattr(s, "site_id", None)
        name = getattr(s, "name", "") or (sid or "GS")
        lat = float(getattr(s, "lat_deg", 0.0))
        lon = float(getattr(s, "lon_deg", 0.0))
        alt_km = getattr(s, "alt_km", None)
        if alt_km is not None:
            core_sites.append(
                GroundSite.from_km(
                    site_id=sid,
                    name=str(name),
                    lat_deg=lat,
                    lon_deg=lon,
                    alt_km=float(alt_km),
                    min_elev_deg=float(getattr(s, "min_elev_deg", 10.0)),
                )
            )
        else:
            core_sites.append(
                GroundSite(
                    name=str(name),
                    lat_deg=lat,
                    lon_deg=lon,
                    alt_m=float(getattr(s, "alt_m", 0.0)),
                    min_elev_deg=float(getattr(s, "min_elev_deg", 10.0)),
                    site_id=sid,
                )
            )

    # build time grid if t not provided
    if t is None:
        if t_start_s is None or t_end_s is None or dt_s is None:
            raise TypeError(
                "compute_access_windows compat requires either (t=..., r_ecef=...) or (t_start_s, t_end_s, dt_s/step_s) plus r_ecef."
            )
        t = np.arange(float(t_start_s), float(t_end_s) + 1e-9, float(dt_s), dtype=float)

    if r_ecef is None:
        raise TypeError("compute_access_windows: r_ecef is required.")

    # ignore any remaining unknown kwargs (compat behavior)
    return compute_access_windows_core(
        t=np.asarray(t, dtype=float), r_ecef=np.asarray(r_ecef, dtype=float), sites=core_sites
    )
