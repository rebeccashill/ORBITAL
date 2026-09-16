# mission_framework/reporting/flight_output.py
"""
Flight path / waypoint output utilities (Aircraft Module A).

Exports:
- Ordered waypoints with timestamps (ETA)
- Optional time series trajectory (if available)
- Minimal JSON/CSV-friendly dictionaries

This module is intentionally lightweight and does not enforce a specific internal format.
It expects:
- Plan.kind == "aircraft"
- Plan.waypoints: list of dicts (each dict may include x/y/z or lat/lon/alt, plus eta/t)
- SimResult.trajectory optionally contains time series state history

Reporting guidance:
- Keep exports simple and readable.
- Pair flight plan tables with constraint reports and summary metrics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PureWindowsPath
from shutil import copy2
from typing import Any, Dict, Iterable, List, Optional
from xml.sax.saxutils import escape

import numpy as np

from mission_framework.core.decision_variables import MutationConfig
from mission_framework.core.json_utils import write_strict_json
from mission_framework.core.objective import ScoreConfig
from mission_framework.core.planner import Planner, PlannerConfig
from mission_framework.core.types import Plan, SimResult, Trajectory
from mission_framework.reporting.operator_review_ui import format_operator_review_ui_html

FLIGHT_PLANNING_EXPORT_NOTICE = (
    "Planning artifact only. ORBITAL does not provide LAANC, waivers, authorizations, "
    "legal approval, autopilot control, or operational clearance."
)

REGULATORY_READINESS_DISCLAIMER = (
    "ORBITAL provides decision support only and is not legal approval. This report does "
    "not provide LAANC, waivers, authorizations, operational clearance, legal advice, "
    "or permission to fly. The pilot-in-command and operator remain responsible for all "
    "required regulatory review, approvals, and compliance decisions."
)

EVIDENCE_BUNDLE_MANIFEST_VERSION = 1
UI_MANIFEST_SCHEMA_VERSION = 1
UI_REQUIRED_TOP_LEVEL_FIELDS = [
    "kind",
    "manifest_version",
    "ui_compatibility",
    "scenario_path",
    "constraint_audit",
    "regulatory_readiness",
    "bundle_completeness",
    "regulatory_documentation_completeness",
    "weather_evidence_readiness",
    "regulatory_evidence_provenance",
    "checksum_evidence_readiness",
    "freshness",
    "artifacts",
    "generated_artifacts",
    "checksum_manifest",
]
UI_ARTIFACT_ENTRY_REQUIRED_FIELDS = ["id", "label", "bundle_path", "present"]
UI_OPTIONAL_FIELD_FALLBACKS = {
    "constraint_audit.mission_id": "scenario filename",
    "constraint_audit.status": "UNKNOWN",
    "constraint_audit.mission_risk": "UNKNOWN",
    "constraint_audit.top_limiting_constraint": "not available",
    "regulatory_readiness.readiness_state": "UNKNOWN",
    "bundle_completeness.score": "n/a",
    "regulatory_documentation_completeness.score": "n/a",
    "weather_evidence_readiness.summary": "No weather evidence status captured.",
    "weather_evidence_readiness.operator_action": "Confirm current weather before release.",
    "regulatory_evidence_provenance.summary": "No regulatory provenance captured.",
    "checksum_evidence_readiness.summary": "Checksum evidence status not captured.",
    "trust_defensibility.uncertainty_robustness_status.summary": (
        "No robustness / uncertainty status captured."
    ),
    "operator_review.operator_decision": "pending operator review",
    "operator_review.reviewer_name": "not provided",
    "operator_review.review_timestamp_utc": "not provided",
}


def flight_plan_table(plan: Plan) -> List[Dict[str, Any]]:
    """
    Return a list of rows for the waypoint plan.

    Expected waypoint dict keys (flexible):
      - id (string)
      - x_m, y_m, z_m OR lat_deg, lon_deg, alt_m
      - eta_s or t_s or time_utc
    """
    if plan.kind != "aircraft":
        raise ValueError(f"flight_plan_table expects plan.kind='aircraft', got '{plan.kind}'")

    wps = plan.waypoints or []
    rows: List[Dict[str, Any]] = []

    for i, wp in enumerate(wps):
        row = {"seq": i}
        row.update(wp)
        # normalize common time key
        if "eta_s" not in row:
            if "t_s" in row:
                row["eta_s"] = row["t_s"]
            elif "time_s" in row:
                row["eta_s"] = row["time_s"]
        rows.append(row)

    return rows


def trajectory_export(sim: SimResult, state_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Export trajectory time series (if present) into a JSON-friendly dict.

    state_names: optional list of names for state columns (length D).
    """
    if sim.trajectory is None:
        return {"present": False}

    traj: Trajectory = sim.trajectory
    t = np.asarray(traj.t, dtype=float)
    x = np.asarray(traj.state, dtype=float)

    out: Dict[str, Any] = {
        "present": True,
        "frame": traj.frame,
        "t_s": t.tolist(),
        "state": x.tolist(),
        "state_names": state_names,
        "metadata": dict(traj.metadata),
    }
    if traj.control is not None:
        out["control"] = np.asarray(traj.control, dtype=float).tolist()
    return out


def export_flight_json(
    plan: Plan,
    sim: Optional[SimResult] = None,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Create (and optionally write) a JSON export containing:
    - waypoint plan table
    - optional trajectory data
    - optional resource traces + scalars

    Returns the payload dict even if out_path is provided.
    """
    payload: Dict[str, Any] = {
        "kind": plan.kind,
        "waypoints": flight_plan_table(plan),
        "plan_metadata": dict(plan.metadata),
    }

    if sim is not None:
        payload["trajectory"] = trajectory_export(sim)
        payload["resources"] = {
            k: np.asarray(v, dtype=float).tolist() for k, v in sim.resources.items()
        }
        payload["scalars"] = dict(sim.scalars)
        payload["sim_metadata"] = dict(sim.metadata)

    if out_path is not None:
        write_strict_json(out_path, payload)

    return payload


def export_waypoints_csv(plan: Plan, out_path: Path) -> None:
    """
    Export waypoint plan as a CSV (human-friendly table).
    """
    rows = flight_plan_table(plan)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect union of keys for header
    keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _float_or_none(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _kml_origin(cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    cfg = cfg or {}
    mission = cfg.get("mission", {}) or {}
    weather = cfg.get("weather", {}) or {}
    resolved_weather = weather.get("resolved", {}) or {}
    location_weather = weather.get("location", {}) or {}
    origin = mission.get("kml_origin", {}) or {}

    lat = (
        _float_or_none(origin.get("latitude_deg"))
        or _float_or_none(resolved_weather.get("latitude_deg"))
        or _float_or_none(location_weather.get("latitude_deg"))
    )
    lon = (
        _float_or_none(origin.get("longitude_deg"))
        or _float_or_none(resolved_weather.get("longitude_deg"))
        or _float_or_none(location_weather.get("longitude_deg"))
    )
    if lat is None or lon is None:
        return None
    return {"latitude_deg": lat, "longitude_deg": lon}


def _local_xy_to_lat_lon(
    x_m: float,
    y_m: float,
    *,
    origin_lat_deg: float,
    origin_lon_deg: float,
) -> Dict[str, float]:
    earth_radius_m = 6_378_137.0
    lat = origin_lat_deg + math.degrees(y_m / earth_radius_m)
    lon = origin_lon_deg + math.degrees(
        x_m / max(1e-9, earth_radius_m * math.cos(math.radians(origin_lat_deg)))
    )
    return {"latitude_deg": lat, "longitude_deg": lon}


def _geo_waypoint(row: Dict[str, Any], origin: Optional[Dict[str, float]]) -> Dict[str, Any]:
    lat = _float_or_none(row.get("lat_deg") or row.get("latitude_deg"))
    lon = _float_or_none(row.get("lon_deg") or row.get("longitude_deg"))
    frame = "wgs84"
    if lat is None or lon is None:
        x = _float_or_none(row.get("x_m"))
        y = _float_or_none(row.get("y_m"))
        if x is None or y is None or origin is None:
            return {**row, "latitude_deg": None, "longitude_deg": None, "frame": "local_only"}
        converted = _local_xy_to_lat_lon(
            x,
            y,
            origin_lat_deg=origin["latitude_deg"],
            origin_lon_deg=origin["longitude_deg"],
        )
        lat = converted["latitude_deg"]
        lon = converted["longitude_deg"]
        frame = "local_enu_derived_wgs84"

    alt = _float_or_none(row.get("alt_m") or row.get("z_m"))
    return {
        **row,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "altitude_m": 0.0 if alt is None else alt,
        "frame": frame,
    }


def build_downstream_flight_plan_rows(
    plan: Plan,
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build simple CSV rows for downstream flight-planning ingestion."""
    origin = _kml_origin(cfg)
    cruise_speed = _float_or_none(plan.metadata.get("cruise_speed_mps"))
    rows: List[Dict[str, Any]] = []
    for row in flight_plan_table(plan):
        geo = _geo_waypoint(row, origin)
        rows.append(
            {
                "sequence": int(row.get("seq", len(rows))),
                "waypoint_id": str(row.get("id", f"WP{len(rows)}")),
                "command": "WAYPOINT",
                "frame": geo.get("frame"),
                "latitude_deg": geo.get("latitude_deg"),
                "longitude_deg": geo.get("longitude_deg"),
                "altitude_m": geo.get("altitude_m"),
                "x_m": row.get("x_m"),
                "y_m": row.get("y_m"),
                "eta_s": row.get("eta_s"),
                "speed_mps": cruise_speed,
                "hold_s": 0.0,
                "planning_only_notice": FLIGHT_PLANNING_EXPORT_NOTICE,
            }
        )
    return rows


def export_autopilot_mission_csv(
    plan: Plan,
    out_path: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Write a simple downstream mission CSV for drone flight-planning tools."""
    rows = build_downstream_flight_plan_rows(plan, cfg=cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sequence",
        "waypoint_id",
        "command",
        "frame",
        "latitude_deg",
        "longitude_deg",
        "altitude_m",
        "x_m",
        "y_m",
        "eta_s",
        "speed_mps",
        "hold_s",
        "planning_only_notice",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return rows


def _kml_coordinates(rows: List[Dict[str, Any]]) -> List[str]:
    coordinates = []
    for row in rows:
        lat = _float_or_none(row.get("latitude_deg"))
        lon = _float_or_none(row.get("longitude_deg"))
        alt = _float_or_none(row.get("altitude_m")) or 0.0
        if lat is None or lon is None:
            continue
        coordinates.append(f"{lon:.8f},{lat:.8f},{alt:.2f}")
    return coordinates


def export_kml_flight_review(
    plan: Plan,
    out_path: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write a KML route preview for visual review in mapping tools."""
    rows = build_downstream_flight_plan_rows(plan, cfg=cfg)
    coordinates = _kml_coordinates(rows)
    if not coordinates:
        raise ValueError("KML export requires lat/lon waypoints or a configured local-frame origin")

    mission_name = str(plan.metadata.get("mission_id", "ORBITAL Mission"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    placemarks = []
    for row in rows:
        coord = _kml_coordinates([row])
        if not coord:
            continue
        placemarks.append(
            "\n".join(
                [
                    "    <Placemark>",
                    f"      <name>{escape(str(row.get('waypoint_id', 'Waypoint')))}</name>",
                    f"      <description>{escape(FLIGHT_PLANNING_EXPORT_NOTICE)}</description>",
                    "      <Point>",
                    f"        <coordinates>{coord[0]}</coordinates>",
                    "      </Point>",
                    "    </Placemark>",
                ]
            )
        )

    kml = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            "  <Document>",
            f"    <name>{escape(mission_name)} - ORBITAL Planning Export</name>",
            f"    <description>{escape(FLIGHT_PLANNING_EXPORT_NOTICE)}</description>",
            "    <Placemark>",
            "      <name>Planned Route</name>",
            f"      <description>{escape(FLIGHT_PLANNING_EXPORT_NOTICE)}</description>",
            "      <LineString>",
            "        <tessellate>1</tessellate>",
            "        <altitudeMode>absolute</altitudeMode>",
            "        <coordinates>",
            f"          {' '.join(coordinates)}",
            "        </coordinates>",
            "      </LineString>",
            "    </Placemark>",
            *placemarks,
            "  </Document>",
            "</kml>",
            "",
        ]
    )
    out_path.write_text(kml, encoding="utf-8")
    return {
        "path": _portable_path_text(out_path),
        "coordinates": len(coordinates),
        "notice": FLIGHT_PLANNING_EXPORT_NOTICE,
    }


def export_flight_planning_artifacts(
    plan: Plan,
    out_dir: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    export_csv: bool = True,
    export_kml: bool = True,
) -> Dict[str, Any]:
    """Export downstream flight-planning artifacts and a planning-only manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, Any] = {
        "kind": "downstream_flight_planning_exports",
        "notice": FLIGHT_PLANNING_EXPORT_NOTICE,
        "artifacts": {},
    }

    if export_csv:
        csv_path = out_dir / "autopilot_mission.csv"
        rows = export_autopilot_mission_csv(plan, csv_path, cfg=cfg)
        artifacts["artifacts"]["autopilot_mission_csv"] = {
            "path": _portable_path_text(csv_path),
            "rows": len(rows),
            "present": csv_path.exists(),
        }

    if export_kml:
        kml_path = out_dir / "mission_review.kml"
        artifacts["artifacts"]["mission_review_kml"] = {
            **export_kml_flight_review(plan, kml_path, cfg=cfg),
            "present": kml_path.exists(),
        }

    readme_lines = [
        "# Downstream Flight-Planning Exports",
        "",
        FLIGHT_PLANNING_EXPORT_NOTICE,
        "",
        "## Files",
        "",
    ]
    for artifact_id, artifact in artifacts["artifacts"].items():
        readme_lines.append(f"- {artifact_id}: `{Path(str(artifact['path'])).name}`")
    (out_dir / "flight_planning_exports.md").write_text(
        "\n".join(readme_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    write_strict_json(out_dir / "flight_planning_exports.json", artifacts)
    return artifacts


def _scalar(sim: Optional[SimResult], key: str, default: Optional[float] = None) -> Optional[float]:
    if sim is None:
        return default
    scalars = getattr(sim, "scalars", {}) or {}
    resources = getattr(sim, "resources", {}) or {}
    if key in scalars:
        return float(scalars[key])
    if key in resources:
        values = np.asarray(resources[key], dtype=float).reshape(-1)
        if values.size:
            return float(values[-1])
    return default


def _fmt_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(number):
        return "n/a"
    suffix = f" {unit}" if unit else ""
    if 0.0 < abs(number) < 1.0:
        return f"{number:.3g}{suffix}"
    return f"{number:.1f}{suffix}"


def _constraint_label(name: str) -> str:
    labels = {
        "all_waypoints_reached": "inspection_completion",
        "battery_nonnegative": "battery_nonnegative",
        "battery_reserve": "battery_reserve",
        "bank_angle_turn_limit": "turn_limit",
        "geofence_no_entry": "geofence_no_entry",
        "geofence_clearance": "geofence_clearance",
    }
    return labels.get(name, name)


def _constraint_by_name(constraints: Any, name: str) -> Optional[Any]:
    if hasattr(constraints, "by_name"):
        return constraints.by_name().get(name)
    for result in getattr(constraints, "results", []) or []:
        if str(getattr(result, "name", "")) == name:
            return result
    return None


def _hard_constraints(constraints: Any) -> Iterable[Any]:
    results = list(getattr(constraints, "results", []) or [])
    return [
        result
        for result in results
        if str(getattr(getattr(result, "severity", ""), "value", result.severity)) == "hard"
    ]


def _recommended_actions(constraints: Any) -> List[str]:
    hard = list(_hard_constraints(constraints))
    failed_names = [str(result.name) for result in hard if not bool(result.is_satisfied)]
    actions: List[str] = []

    if not failed_names:
        actions.append(
            "Proceed if the pilot-in-command confirms airspace authorization, crew readiness, "
            "and field conditions."
        )
        low_reserve = next((r for r in hard if str(r.name) == "battery_reserve"), None)
        if low_reserve is not None and float(low_reserve.min_margin) < 75.0:
            actions.append(
                "Reduce route length or plan a relaunch / battery swap to widen reserve."
            )
        actions.append("Wait for better wind if observed conditions exceed the scenario model.")
        actions.append(
            "Maintain the modeled geofence clearance before export to any flight system."
        )
        return actions

    if any("battery" in name for name in failed_names):
        actions.append("Reduce route length or plan a relaunch / battery swap.")
    if any("geofence" in name for name in failed_names):
        actions.append("Adjust geofence clearance or reroute the inspection corridor.")
    if "all_waypoints_reached" in failed_names:
        actions.append("Reduce the route or split the inspection into shorter sorties.")
    if "bank_angle_turn_limit" in failed_names:
        actions.append("Lower cruise speed or increase turn spacing.")
    actions.append("Wait for better wind before retrying if winds are the binding constraint.")
    return actions


def _yes_no_unknown(value: Any) -> str:
    if value is None:
        return "unknown"
    return "yes" if bool(value) else "no"


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    if isinstance(value, Iterable) and not isinstance(value, (dict, bytes)):
        items = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    return []


def _regulatory_time_window(regulatory: Dict[str, Any]) -> Dict[str, Any]:
    window = regulatory.get("operating_time_window")
    if not isinstance(window, dict):
        return {}
    return {
        "start_utc": window.get("start_utc"),
        "end_utc": window.get("end_utc"),
    }


def _regulatory_metadata(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    regulatory = (cfg or {}).get("regulatory", {}) or {}
    notice = regulatory.get(
        "documentation_only_notice",
        "Regulatory fields are planning documentation only. ORBITAL does not provide "
        "LAANC, waivers, authorizations, legal approval, or operational clearance.",
    )
    return {
        "documentation_only": True,
        "laanc_required": regulatory.get("laanc_required"),
        "waiver_or_authorization_required": regulatory.get("waiver_or_authorization_required"),
        "airspace_class": regulatory.get("airspace_class"),
        "visual_observer_required": regulatory.get("visual_observer_required"),
        "ground_risk_population_note": regulatory.get("ground_risk_population_note"),
        "authorization_id": regulatory.get("authorization_id"),
        "authorization_authority": regulatory.get("authorization_authority")
        or regulatory.get("authority"),
        "approving_authority_source": regulatory.get("approving_authority_source"),
        "authorization_date_checked_utc": regulatory.get("authorization_date_checked_utc")
        or regulatory.get("date_checked_utc"),
        "authorization_expiration_date": regulatory.get("authorization_expiration_date"),
        "operator_confirmation_status": regulatory.get("operator_confirmation_status"),
        "evidence_freshness_max_age_hours": regulatory.get("evidence_freshness_max_age_hours"),
        "operating_altitude_limit_m": regulatory.get("operating_altitude_limit_m"),
        "operating_time_window": _regulatory_time_window(regulatory),
        "required_crew_roles": _string_list(regulatory.get("required_crew_roles")),
        "special_conditions_limitations": _string_list(
            regulatory.get("special_conditions_limitations")
        ),
        "emergency_contingency_plan": regulatory.get("emergency_contingency_plan"),
        "operating_assumptions": _string_list(regulatory.get("operating_assumptions")),
        "unresolved_items": _string_list(regulatory.get("unresolved_items")),
        "documentation_only_notice": notice,
        "decision_support_disclaimer": REGULATORY_READINESS_DISCLAIMER,
    }


def _weather_metadata(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    weather = (cfg or {}).get("weather", {}) or {}
    resolved = weather.get("resolved", {}) or {}
    if not resolved:
        return {}
    return {
        "provider": resolved.get("provider"),
        "source": resolved.get("source"),
        "timestamp_utc": resolved.get("timestamp_utc"),
        "location_name": resolved.get("location_name"),
        "latitude_deg": resolved.get("latitude_deg"),
        "longitude_deg": resolved.get("longitude_deg"),
        "forecast_window_start_utc": resolved.get("forecast_window_start_utc"),
        "forecast_window_hours": resolved.get("forecast_window_hours"),
        "wind_speed_mps": resolved.get("wind_speed_mps"),
        "wind_direction_deg": resolved.get("wind_direction_deg"),
        "wind_gust_mps": resolved.get("wind_gust_mps"),
        "visibility_m": resolved.get("visibility_m"),
        "precipitation_mm": resolved.get("precipitation_mm"),
        "temperature_C": resolved.get("temperature_C"),
        "fallback_used": resolved.get("fallback_used"),
        "fallback_reason": resolved.get("fallback_reason"),
        "live_fetch_enabled": resolved.get("live_fetch_enabled"),
        "applied_to_wind": weather.get("applied_to_wind"),
        "freshness_max_age_hours": weather.get("freshness_max_age_hours")
        or weather.get("evidence_freshness_max_age_hours"),
        "live_provider_configured": weather.get("use_live") is True,
    }


def _parse_utc_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hours_between(start: Any, end: Any) -> Optional[float]:
    start_dt = _parse_utc_datetime(start)
    end_dt = _parse_utc_datetime(end)
    if start_dt is None or end_dt is None:
        return None
    return max(0.0, (end_dt - start_dt).total_seconds() / 3600.0)


def _float_from(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _source_is_sample_or_offline(source: Any) -> bool:
    normalized = str(source or "").strip().lower()
    return "sample" in normalized or "offline" in normalized or "demo" in normalized


def _weather_evidence_readiness(
    weather: Dict[str, Any],
    *,
    generated_timestamp_utc: str,
) -> Dict[str, Any]:
    max_age_hours = _float_from(weather.get("freshness_max_age_hours"), 2.0)
    timestamp = weather.get("timestamp_utc")
    source = weather.get("source") or "not provided"
    provider = weather.get("provider") or "not provided"
    age_hours = _hours_between(timestamp, generated_timestamp_utc)
    sample_or_offline = _source_is_sample_or_offline(source)
    fallback_used = weather.get("fallback_used")
    live_fetch_enabled = weather.get("live_fetch_enabled")
    missing = not weather or not timestamp or source == "not provided"
    stale = age_hours is not None and age_hours > max_age_hours

    if missing:
        mode = "missing"
        freshness_status = "missing"
        status = "MISSING"
        operator_action = (
            "Attach current weather evidence and confirm launch-time conditions outside "
            "ORBITAL before release. Operator should verify launch-time weather."
        )
    elif stale:
        mode = "sample" if sample_or_offline else "fallback" if fallback_used else "live"
        freshness_status = "stale"
        status = "STALE"
        operator_action = (
            "Refresh weather evidence close to launch and keep the source timestamp with "
            "the evidence bundle. Operator should verify field conditions."
        )
    elif sample_or_offline:
        mode = "sample"
        freshness_status = "sample"
        status = "SAMPLE"
        operator_action = (
            "Replace sample or offline weather with current field weather before "
            "operational use. Operator should verify the source outside ORBITAL."
        )
    elif fallback_used is True:
        mode = "fallback"
        freshness_status = "fallback"
        status = "FALLBACK USED"
        operator_action = (
            "Verify current field weather because the bundle used fallback weather data. "
            "Operator should verify the source outside ORBITAL."
        )
    elif live_fetch_enabled is True:
        mode = "live"
        freshness_status = "fresh"
        status = "LIVE"
        operator_action = (
            "Confirm the live weather timestamp remains inside the operator's launch "
            "weather window. Operator should verify field conditions."
        )
    else:
        mode = "packaged"
        freshness_status = "packaged"
        status = "PACKAGED"
        operator_action = (
            "Confirm packaged weather evidence against launch-time field conditions. "
            "Operator should verify the source outside ORBITAL."
        )

    age_text = "unknown age" if age_hours is None else f"{age_hours:.1f} hours old"
    max_age_text = f"{max_age_hours:g}-hour review window"
    timestamp_text = timestamp or "not provided"
    if status == "MISSING":
        summary = (
            "MISSING: no usable weather evidence timestamp or source was recorded. "
            "Attach current weather evidence before release review."
        )
    elif status == "STALE":
        summary = (
            f"STALE: weather evidence is {age_text}, outside the {max_age_text}. "
            f"Source: {source}; timestamp: {timestamp_text}."
        )
    elif status == "SAMPLE":
        summary = (
            f"SAMPLE: weather evidence uses sample or offline data from {source}. "
            f"Replace it with current field weather before operational use. "
            f"Timestamp: {timestamp_text}."
        )
    elif status == "FALLBACK USED":
        summary = (
            f"FALLBACK USED: weather evidence came from fallback data from {source}. "
            f"Verify current field weather before release. Timestamp: {timestamp_text}."
        )
    elif status == "LIVE":
        summary = (
            f"LIVE: weather evidence timestamp {timestamp_text} is inside the "
            f"{max_age_text}. Source: {source}."
        )
    else:
        summary = (
            f"{status}: packaged weather evidence from {source}. Confirm it against "
            f"launch-time field conditions. Timestamp: {timestamp_text}."
        )
    return {
        "documentation_only": True,
        "status": status,
        "mode": mode,
        "source": source,
        "provider": provider,
        "timestamp_utc": timestamp or "not provided",
        "generated_timestamp_utc": generated_timestamp_utc,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "freshness_max_age_hours": max_age_hours,
        "freshness_status": freshness_status,
        "fallback_used": fallback_used,
        "fallback_reason": weather.get("fallback_reason"),
        "sample_or_offline": sample_or_offline,
        "live_fetch_enabled": live_fetch_enabled,
        "live_provider_configured": weather.get("live_provider_configured"),
        "live_provider_hook": {
            "provider": provider,
            "configured": weather.get("live_provider_configured") is True,
            "required": False,
            "documentation_only": True,
            "note": (
                "Live weather provider integration can populate this evidence block, "
                "but ORBITAL does not require live integration or verify launch "
                "authorization."
            ),
        },
        "operator_action": operator_action,
        "summary": summary,
        "notice": (
            "Weather evidence supports operator review only. ORBITAL does not certify "
            "weather, approve launch, or provide operational clearance."
        ),
    }


def _regulatory_evidence_provenance(
    regulatory: Dict[str, Any],
    evidence: Dict[str, Any],
    *,
    generated_timestamp_utc: str,
) -> Dict[str, Any]:
    authorization_needed = (
        regulatory.get("laanc_required") is True
        or regulatory.get("waiver_or_authorization_required") is True
    )
    source = (
        evidence.get("approving_authority_source")
        or regulatory.get("approving_authority_source")
        or "not provided"
    )
    date_checked = (
        regulatory.get("authorization_date_checked_utc")
        or evidence.get("authorization_date_checked_utc")
        or regulatory.get("date_checked_utc")
    )
    expiration = evidence.get("authorization_expiration_date") or regulatory.get(
        "authorization_expiration_date"
    )
    authority = (
        regulatory.get("authorization_authority")
        or evidence.get("authorization_authority")
        or regulatory.get("airspace_class")
        or "not provided"
    )
    confirmation_status = (
        regulatory.get("operator_confirmation_status")
        or evidence.get("operator_confirmation_status")
        or ("pending_operator_confirmation" if authorization_needed else "not_required")
    )
    max_age_hours = _float_from(regulatory.get("evidence_freshness_max_age_hours"), 24.0)
    checked_age_hours = _hours_between(date_checked, generated_timestamp_utc)
    stale = checked_age_hours is not None and checked_age_hours > max_age_hours
    expiration_dt = _parse_utc_datetime(expiration)
    generated_dt = _parse_utc_datetime(generated_timestamp_utc)
    expired = (
        expiration_dt is not None and generated_dt is not None and expiration_dt < generated_dt
    )
    missing_source = authorization_needed and source == "not provided"
    missing_date_checked = authorization_needed and not date_checked
    pending_confirmation = str(confirmation_status).strip().lower() not in {
        "confirmed",
        "operator_confirmed",
        "verified_outside_orbital",
        "not_required",
    }

    if expired:
        status = "EXPIRED"
        operator_action = "Replace expired authorization evidence before operator release."
    elif missing_source or missing_date_checked:
        status = "MISSING"
        operator_action = (
            "Document authorization source and date checked outside ORBITAL before "
            "operator release. Operator should verify regulatory inputs."
        )
    elif stale:
        status = "STALE"
        operator_action = (
            "Refresh regulatory evidence checks before relying on this bundle for review. "
            "Operator should verify regulatory inputs."
        )
    elif pending_confirmation:
        status = "PENDING OPERATOR CONFIRMATION"
        operator_action = (
            "Operator must confirm authorization, restrictions, and current airspace "
            "status outside ORBITAL. Operator should verify regulatory inputs."
        )
    else:
        status = "DOCUMENTED"
        operator_action = (
            "Keep source, date checked, expiration, and confirmation record with the bundle. "
            "Operator should verify regulatory inputs."
        )

    checked_text = date_checked or "not provided"
    expiration_text = expiration or "not provided"
    checked_age_text = (
        "unknown age" if checked_age_hours is None else f"{checked_age_hours:.1f} hours old"
    )
    max_age_text = f"{max_age_hours:g}-hour review window"
    if status == "EXPIRED":
        summary = (
            f"EXPIRED: regulatory evidence expired on {expiration_text}. "
            f"Source: {source}; checked: {checked_text}; authority: {authority}; "
            f"confirmation: {confirmation_status}."
        )
    elif status == "MISSING":
        summary = (
            "MISSING: regulatory evidence needs a documented source and date checked "
            f"before release review. Source: {source}; checked: {checked_text}; "
            f"authority: {authority}; confirmation: {confirmation_status}."
        )
    elif status == "STALE":
        summary = (
            f"STALE: regulatory evidence was checked {checked_age_text}, outside "
            f"the {max_age_text}. Source: {source}; checked: {checked_text}; "
            f"expiration: {expiration_text}; authority: {authority}; "
            f"confirmation: {confirmation_status}."
        )
    elif status == "PENDING OPERATOR CONFIRMATION":
        summary = (
            "PENDING OPERATOR CONFIRMATION: authorization evidence is documented, "
            "but the operator has not confirmed it outside ORBITAL. "
            f"Source: {source}; checked: {checked_text}; expiration: {expiration_text}; "
            f"authority: {authority}; confirmation: {confirmation_status}."
        )
    else:
        summary = (
            f"DOCUMENTED: regulatory evidence is documented for review. Source: {source}; "
            f"checked: {checked_text}; expiration: {expiration_text}; "
            f"authority: {authority}; confirmation: {confirmation_status}."
        )

    return {
        "documentation_only": True,
        "status": status,
        "source": source,
        "date_checked_utc": date_checked or "not provided",
        "expiration_date": expiration or "not provided",
        "authority": authority,
        "operator_confirmation_status": confirmation_status,
        "authorization_required": authorization_needed,
        "checked_age_hours": (
            round(checked_age_hours, 2) if checked_age_hours is not None else None
        ),
        "freshness_max_age_hours": max_age_hours,
        "freshness_status": "stale" if stale else "fresh" if date_checked else "missing",
        "expired": expired,
        "operator_action": operator_action,
        "summary": summary,
        "notice": (
            "Regulatory evidence provenance is documentation-only. ORBITAL does not "
            "grant approval, authorization, LAANC, legal advice, or operational clearance."
        ),
    }


def _optional_metadata_block(
    cfg: Optional[Dict[str, Any]],
    section: str,
    keys: Iterable[str],
) -> Dict[str, Any]:
    block = (cfg or {}).get(section, {}) or {}
    return {key: block.get(key) for key in keys if block.get(key) is not None}


def _mission_metadata(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _optional_metadata_block(
        cfg,
        "mission_metadata",
        (
            "operator",
            "aircraft_id",
            "pilot",
            "organization",
            "asset_owner",
        ),
    )


def _fleet_metadata(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _optional_metadata_block(
        cfg,
        "fleet_metadata",
        (
            "drone_model",
            "battery_pack_id",
            "sensor_payload",
            "inspection_type",
        ),
    )


def _resource_values(sim: SimResult, key: str) -> np.ndarray:
    return np.asarray(sim.resources.get(key, []), dtype=float).reshape(-1)


def _max_horizontal_wind_mps(sim: SimResult) -> Optional[float]:
    east = _resource_values(sim, "wind_east_mps")
    north = _resource_values(sim, "wind_north_mps")
    if east.size == 0 or north.size == 0:
        return None
    n = min(east.size, north.size)
    return float(np.max(np.hypot(east[:n], north[:n])))


def _status_from_margin(margin: Optional[float], warning_margin: float) -> str:
    if margin is None:
        return "unknown"
    if margin < 0.0:
        return "fail"
    if margin < warning_margin:
        return "warning"
    return "pass"


def _risk_points(margin: Optional[float], warning_margin: float) -> float:
    warn = max(float(warning_margin), 1e-6)
    if margin is None:
        return 50.0
    if margin < 0.0:
        return float(min(100.0, 80.0 + min(20.0, abs(float(margin)) / warn * 20.0)))
    if margin < warn:
        return float(40.0 + (warn - float(margin)) / warn * 30.0)
    return float(max(0.0, 30.0 * (1.0 - min(float(margin) / (3.0 * warn), 1.0))))


CONSTRAINT_GROUP_DETAILS: Dict[str, Dict[str, Any]] = {
    "battery_reserve": {
        "category": "energy",
        "category_label": "Energy / battery reserve",
        "plain_english": (
            "Checks whether the planned sortie lands with the operator-required battery "
            "reserve still available."
        ),
        "why_this_matters_to_operator": (
            "A BVLOS inspection needs enough remaining energy for delay, diversion, "
            "recovery, and conservative abort decisions."
        ),
        "operator_actions": {
            "pass": (
                "Keep the reserve assumption, confirm launch battery state, and brief "
                "abort reserve before dispatch."
            ),
            "warning": (
                "Review payload draw and route length; trim inspection scope or stage a "
                "battery swap before release."
            ),
            "fail": (
                "Do not fly as modeled; shorten the mission, add a relaunch / battery "
                "swap, or use a higher-endurance aircraft."
            ),
            "unknown": (
                "Document battery capacity, reserve policy, and simulated final battery "
                "before operator review."
            ),
        },
    },
    "wind_weather": {
        "category": "weather",
        "category_label": "Weather / wind margin",
        "plain_english": (
            "Checks whether modeled or forecast wind stays below the configured safe "
            "operating limit."
        ),
        "why_this_matters_to_operator": (
            "Wind reduces endurance, increases tracking error, and can turn a feasible "
            "route into a recovery or containment problem."
        ),
        "operator_actions": {
            "pass": (
                "Confirm launch-time weather against operator minimums and keep the "
                "forecast source with the mission package."
            ),
            "warning": (
                "Delay launch, lower mission scope, or require a field weather update "
                "before final go/no-go."
            ),
            "fail": (
                "Do not fly as modeled; wait for safer weather or redesign the sortie "
                "for lower exposure."
            ),
            "unknown": (
                "Add a weather source, timestamp, and wind assumptions before operator " "review."
            ),
        },
    },
    "geofence_clearance": {
        "category": "airspace_geometry",
        "category_label": "Geofence / no-fly-zone clearance",
        "plain_english": (
            "Checks whether the route remains outside no-fly zones and preserves the "
            "configured stand-off buffer."
        ),
        "why_this_matters_to_operator": (
            "Geofence clearance protects people, assets, restricted areas, and customer "
            "boundaries when navigation or wind uncertainty appears."
        ),
        "operator_actions": {
            "pass": (
                "Keep the geofence file and route review in the evidence bundle, then "
                "confirm site boundaries before flight."
            ),
            "warning": (
                "Move waypoints farther from the boundary or increase the clearance "
                "buffer before release."
            ),
            "fail": (
                "Do not fly as modeled; reroute around the violation or redefine the "
                "operating area."
            ),
            "unknown": ("Document geofence inputs and minimum clearance before operator review."),
        },
    },
    "route_completion": {
        "category": "mission_completion",
        "category_label": "Route completion",
        "plain_english": (
            "Checks whether the candidate plan reaches all required inspection points."
        ),
        "why_this_matters_to_operator": (
            "Incomplete route coverage can waste a crew deployment and create pressure "
            "to improvise in the field."
        ),
        "operator_actions": {
            "pass": (
                "Confirm the waypoint list matches the inspection scope and brief any "
                "acceptable skipped-point policy."
            ),
            "warning": (
                "Review the missed-point risk and consider splitting the route into "
                "shorter sorties."
            ),
            "fail": (
                "Do not treat the plan as inspection-ready; reduce scope, split sorties, "
                "or move the launch point."
            ),
            "unknown": (
                "Document required waypoints and simulated completion status before "
                "operator review."
            ),
        },
    },
    "turn_bank_feasibility": {
        "category": "flight_dynamics",
        "category_label": "Turn / bank feasibility",
        "plain_english": (
            "Checks whether planned turns stay within configured bank-angle and turn-rate "
            "capability."
        ),
        "why_this_matters_to_operator": (
            "Overly aggressive turns can break route tracking, increase energy use, and "
            "reduce safety margins near assets or geofences."
        ),
        "operator_actions": {
            "pass": (
                "Keep the planned speed and turn assumptions, then verify they match the "
                "aircraft operating envelope."
            ),
            "warning": (
                "Lower cruise speed, add waypoint spacing, or smooth the route before " "release."
            ),
            "fail": (
                "Do not fly as modeled; redesign the route geometry or aircraft speed " "profile."
            ),
            "unknown": (
                "Document bank-angle limits, speed assumptions, and route geometry before "
                "operator review."
            ),
        },
    },
}


def _constraint_status_meaning(status: str) -> str:
    normalized = str(status).lower()
    if normalized == "pass":
        return "Modeled margin is above the configured review threshold."
    if normalized == "warning":
        return "Modeled margin is positive, but close enough to require operator review."
    if normalized == "fail":
        return "Modeled margin is negative; modify the mission before release."
    return "ORBITAL does not have enough data to classify this constraint group."


def _check(
    *,
    check_id: str,
    label: str,
    margin: Optional[float],
    unit: str,
    margin_source: str,
    warning_margin: float,
    warning_margin_source: str,
    observed: Dict[str, Any],
    recommendation: str,
) -> Dict[str, Any]:
    points = _risk_points(margin, warning_margin)
    status = _status_from_margin(margin, warning_margin)
    group = CONSTRAINT_GROUP_DETAILS.get(
        check_id,
        {
            "category": "other",
            "category_label": label,
            "plain_english": "Reviews an operator-defined mission feasibility constraint.",
            "why_this_matters_to_operator": (
                "This constraint may affect whether the mission can be safely and "
                "defensibly released."
            ),
            "operator_actions": {},
        },
    )
    actions = group.get("operator_actions") or {}
    recommended_operator_action = str(actions.get(status) or recommendation)
    return {
        "id": check_id,
        "label": label,
        "category": group.get("category"),
        "category_label": group.get("category_label", label),
        "status": status,
        "status_meaning": _constraint_status_meaning(status),
        "plain_english": group.get("plain_english"),
        "why_this_matters_to_operator": group.get("why_this_matters_to_operator"),
        "margin": {"value": margin, "unit": unit, "source": margin_source},
        "warning_margin": {
            "value": float(warning_margin),
            "unit": unit,
            "source": warning_margin_source,
        },
        "risk_points": float(points),
        "observed": observed,
        "recommendation": recommendation,
        "recommended_operator_action": recommended_operator_action,
    }


def _named_margin(constraints: Any, name: str) -> Optional[float]:
    result = _constraint_by_name(constraints, name)
    if result is None:
        return None
    return float(result.min_margin)


def _field_value(name: str, value: Any, unit: str, source: str) -> Dict[str, Any]:
    return {"name": name, "value": value, "unit": unit, "source": source}


def _model_assumptions_report(
    plan: Plan,
    sim: SimResult,
    *,
    cfg: Dict[str, Any],
    robustness: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    vehicle = cfg.get("vehicle", {}) or {}
    initial_state = cfg.get("initial_state", {}) or {}
    wind_cfg = cfg.get("wind", {}) or {}
    weather = _weather_metadata(cfg)
    geofence_cfg = cfg.get("geofence", {}) or {}
    mission_cfg = cfg.get("mission", {}) or {}
    constraints_cfg = cfg.get("constraints", {}) or {}
    robustness_cfg = cfg.get("robustness", {}) or {}
    robustness_summary = robustness or {}
    waypoint_total = _scalar(sim, "waypoints_total")
    waypoint_count = len(mission_cfg.get("waypoints", []) or [])
    if waypoint_count == 0 and waypoint_total is not None:
        waypoint_count = int(waypoint_total)
    geofence_zones = list(geofence_cfg.get("no_fly_zones", []) or [])
    route_source = (
        plan.metadata.get("route_source") or mission_cfg.get("route_geojson_path") or "yaml"
    )
    robustness_cases = robustness_summary.get("cases", robustness_cfg.get("cases", 0))

    return [
        {
            "id": "battery",
            "label": "Battery / energy model",
            "source": "scenario.initial_state, scenario.vehicle, simulation scalars, and battery constraints",
            "inputs": [
                _field_value(
                    "initial battery",
                    initial_state.get("battery_Wh", vehicle.get("battery_capacity_Wh")),
                    "Wh",
                    "initial_state.battery_Wh",
                ),
                _field_value(
                    "battery capacity",
                    vehicle.get("battery_capacity_Wh"),
                    "Wh",
                    "vehicle.battery_capacity_Wh",
                ),
                _field_value(
                    "required battery reserve",
                    vehicle.get("battery_reserve_Wh"),
                    "Wh",
                    "vehicle.battery_reserve_Wh",
                ),
                _field_value(
                    "final simulated battery",
                    _scalar(sim, "final_battery_Wh"),
                    "Wh",
                    "simulation.scalars.final_battery_Wh",
                ),
                _field_value(
                    "energy used",
                    _scalar(sim, "energy_used_Wh"),
                    "Wh",
                    "simulation.scalars.energy_used_Wh",
                ),
            ],
            "assumption": (
                "Battery feasibility is based on the configured capacity, initial charge, "
                "reserve policy, and simplified power model coefficients."
            ),
            "operator_review_note": (
                "Confirm aircraft battery health, payload draw, temperature effects, and "
                "abort reserve outside ORBITAL before release."
            ),
        },
        {
            "id": "wind",
            "label": "Wind / weather model",
            "source": "scenario.wind, scenario.weather, weather.resolved, and simulation wind resources",
            "inputs": [
                _field_value(
                    "wind model type",
                    wind_cfg.get("type", "sinusoidal"),
                    "",
                    "wind.type",
                ),
                _field_value(
                    "maximum safe wind",
                    wind_cfg.get("max_safe_wind_mps"),
                    "m/s",
                    "wind.max_safe_wind_mps",
                ),
                _field_value(
                    "weather wind gust",
                    weather.get("wind_gust_mps"),
                    "m/s",
                    "weather.resolved.wind_gust_mps",
                ),
                _field_value(
                    "weather source",
                    weather.get("source"),
                    "",
                    "weather.resolved.source",
                ),
                _field_value(
                    "weather timestamp",
                    weather.get("timestamp_utc"),
                    "UTC",
                    "weather.resolved.timestamp_utc",
                ),
            ],
            "assumption": (
                "Wind feasibility compares the modeled or weather-provided wind exposure "
                "against the configured safe operating limit."
            ),
            "operator_review_note": (
                "Refresh field weather and gust observations close to launch, especially "
                "when offline or sample weather is used."
            ),
        },
        {
            "id": "geofence",
            "label": "Geofence / no-fly-zone model",
            "source": "scenario.geofence, imported GeoJSON zones, and simulation geofence scalars",
            "inputs": [
                _field_value(
                    "required clearance",
                    geofence_cfg.get("clearance_m"),
                    "m",
                    "geofence.clearance_m",
                ),
                _field_value(
                    "manual no-fly zones",
                    len(geofence_zones),
                    "zones",
                    "geofence.no_fly_zones",
                ),
                _field_value(
                    "GeoJSON geofence path",
                    geofence_cfg.get("geojson_path"),
                    "",
                    "geofence.geojson_path",
                ),
                _field_value(
                    "minimum simulated clearance",
                    _scalar(sim, "geofence_min_clearance_m"),
                    "m",
                    "simulation.scalars.geofence_min_clearance_m",
                ),
            ],
            "assumption": (
                "Geofence feasibility treats configured polygons and imported GeoJSON "
                "zones as the planning boundary source."
            ),
            "operator_review_note": (
                "Confirm site boundaries, customer buffers, and launch/recovery areas on "
                "current maps before export or dispatch."
            ),
        },
        {
            "id": "route_completion",
            "label": "Route completion model",
            "source": "scenario.mission, route GeoJSON, plan waypoints, and simulation completion scalars",
            "inputs": [
                _field_value(
                    "route source",
                    route_source,
                    "",
                    "mission.route_geojson_path or mission.waypoints",
                ),
                _field_value(
                    "fixed route order",
                    mission_cfg.get("fixed_order"),
                    "boolean",
                    "mission.fixed_order",
                ),
                _field_value(
                    "inspection waypoints",
                    waypoint_count,
                    "waypoints",
                    "mission.waypoints",
                ),
                _field_value(
                    "waypoints completed",
                    _scalar(sim, "waypoints_completed"),
                    "waypoints",
                    "simulation.scalars.waypoints_completed",
                ),
                _field_value(
                    "route completion enforced",
                    constraints_cfg.get("enforce_inspection_completion"),
                    "boolean",
                    "constraints.enforce_inspection_completion",
                ),
            ],
            "assumption": (
                "The route is considered complete only when the simulation reaches the "
                "required inspection waypoints under the configured reach radius."
            ),
            "operator_review_note": (
                "Confirm the waypoint list matches the inspection scope and define any "
                "acceptable skipped-point policy before dispatch."
            ),
        },
        {
            "id": "turn_feasibility",
            "label": "Turn / bank feasibility model",
            "source": "scenario.vehicle, simulated yaw-rate resources, and bank-angle constraint margins",
            "inputs": [
                _field_value(
                    "bank limit",
                    vehicle.get("bank_max_deg"),
                    "deg",
                    "vehicle.bank_max_deg",
                ),
                _field_value(
                    "planned cruise speed",
                    plan.metadata.get("cruise_speed_mps"),
                    "m/s",
                    "plan.metadata.cruise_speed_mps",
                ),
                _field_value(
                    "minimum airspeed",
                    vehicle.get("min_speed_mps"),
                    "m/s",
                    "vehicle.min_speed_mps",
                ),
                _field_value(
                    "maximum airspeed",
                    vehicle.get("max_speed_mps"),
                    "m/s",
                    "vehicle.max_speed_mps",
                ),
            ],
            "assumption": (
                "Turn feasibility uses a simplified bank-angle/yaw-rate envelope rather "
                "than aircraft-specific autopilot tracking or detailed aerodynamics."
            ),
            "operator_review_note": (
                "Confirm the route geometry, turn spacing, and selected speed are within "
                "the aircraft operating envelope."
            ),
        },
        {
            "id": "robustness",
            "label": "Robustness model",
            "source": "scenario.robustness and planner robustness summary",
            "inputs": [
                _field_value(
                    "robustness cases configured",
                    robustness_cfg.get("cases", 0),
                    "cases",
                    "robustness.cases",
                ),
                _field_value(
                    "robustness cases run",
                    robustness_cases,
                    "cases",
                    "robustness summary",
                ),
                _field_value(
                    "wind scale range",
                    robustness_cfg.get("wind_scale_range"),
                    "multiplier",
                    "robustness.wind_scale_range",
                ),
                _field_value(
                    "battery variation",
                    robustness_cfg.get("battery_variation_pct"),
                    "fraction",
                    "robustness.battery_variation_pct",
                ),
                _field_value(
                    "hard pass rate",
                    robustness_summary.get("hard_pass_rate"),
                    "ratio",
                    "robustness summary.hard_pass_rate",
                ),
            ],
            "assumption": (
                "Robustness reflects configured Monte Carlo perturbations only; it is not "
                "a certification, reliability guarantee, or live safety monitor."
            ),
            "operator_review_note": (
                "Increase robustness cases or add scenario-specific uncertainty ranges "
                "when margin sensitivity matters."
            ),
        },
    ]


def _model_limitations(cfg: Dict[str, Any], weather: Dict[str, Any]) -> List[Dict[str, Any]]:
    weather_cfg = cfg.get("weather", {}) or {}
    source = str(weather.get("source") or "").lower()
    offline_or_sample = (
        bool(weather.get("fallback_used"))
        or bool(weather_cfg.get("use_live") is False)
        or "offline" in source
        or "sample" in source
    )
    return [
        {
            "id": "offline_sample_weather",
            "applies": offline_or_sample,
            "limitation": (
                "Weather may come from offline, fallback, or sample inputs. ORBITAL "
                "records the source and timestamp, but the operator must verify current "
                "field weather before release."
            ),
        },
        {
            "id": "simplified_flight_dynamics",
            "applies": True,
            "limitation": (
                "Aircraft dynamics are simplified for feasibility planning. ORBITAL does "
                "not model every autopilot behavior, controller response, payload effect, "
                "battery aging factor, sensor constraint, or emergency maneuver."
            ),
        },
        {
            "id": "decision_support_only",
            "applies": True,
            "limitation": (
                "Constraint margins are planning evidence for operator review. They do not "
                "approve a flight, issue authorization, or replace pilot-in-command judgment."
            ),
        },
    ]


def _top_limiting_constraint_selection(checks_sorted: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not checks_sorted:
        return {
            "method": "risk_points_descending",
            "selected_constraint_id": None,
            "explanation": "No constraint groups were available to rank.",
            "ranking": [],
        }

    top = checks_sorted[0]
    margin = top.get("margin") or {}
    warning_margin = top.get("warning_margin") or {}
    ranking = []
    for index, check in enumerate(checks_sorted, start=1):
        ranking.append(
            {
                "rank": index,
                "id": check.get("id"),
                "label": check.get("label"),
                "status": check.get("status"),
                "risk_points": check.get("risk_points"),
                "margin": check.get("margin"),
            }
        )
    return {
        "method": "risk_points_descending",
        "risk_points_definition": (
            "Risk points increase when a constraint fails, is inside its warning band, "
            "or has little positive margin relative to its warning threshold."
        ),
        "selected_constraint_id": top.get("id"),
        "selected_label": top.get("label"),
        "selected_status": top.get("status"),
        "selected_risk_points": top.get("risk_points"),
        "selected_margin": margin,
        "selected_warning_margin": warning_margin,
        "explanation": (
            f"{top.get('label', 'The top constraint')} was selected because it had "
            f"the highest risk_points value ({_fmt_value(top.get('risk_points'))}) "
            f"among {len(checks_sorted)} audited constraint groups. Its margin was "
            f"{_fmt_value(margin.get('value'), margin.get('unit', ''))} against a "
            f"warning threshold of "
            f"{_fmt_value(warning_margin.get('value'), warning_margin.get('unit', ''))}."
        ),
        "ranking": ranking,
    }


def _scenario_path_text(scenario_path: Optional[Any], cfg: Dict[str, Any]) -> str:
    if scenario_path:
        try:
            return _portable_path_text(Path(str(scenario_path)))
        except OSError:
            return str(scenario_path).replace("\\", "/")
    configured = cfg.get("_scenario_path")
    return _portable_path_text(Path(str(configured))) if configured else "not provided"


def _reproducibility_report(
    *,
    cfg: Dict[str, Any],
    scenario_path: Optional[Any],
    command_used: Optional[Any],
    robustness: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    planner = cfg.get("planner", {}) or {}
    robustness_cfg = cfg.get("robustness", {}) or {}
    robustness_summary = robustness or {}
    return {
        "scenario_path": _scenario_path_text(scenario_path, cfg),
        "seed": planner.get("seed"),
        "iterations": planner.get("iterations"),
        "restarts": planner.get("restarts"),
        "robustness_cases_configured": robustness_cfg.get("cases", 0),
        "robustness_cases_run": robustness_summary.get(
            "cases",
            0 if int(robustness_cfg.get("cases", 0) or 0) == 0 else None,
        ),
        "command": _command_metadata(command_used),
        "orbital_version": _orbital_version(),
    }


def build_inspection_constraint_audit(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
    scenario_path: Optional[Any] = None,
    command_used: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build a drone-inspection-specific audit payload from a solved aircraft mission."""
    cfg = cfg or {}
    vehicle = cfg.get("vehicle", {}) or {}
    wind_cfg = cfg.get("wind", {}) or {}
    geofence_cfg = cfg.get("geofence", {}) or {}
    weather = _weather_metadata(cfg)
    mission_metadata = _mission_metadata(cfg)
    fleet_metadata = _fleet_metadata(cfg)

    reserve_wh = float(vehicle.get("battery_reserve_Wh", 0.0))
    battery_warning_wh = max(50.0, reserve_wh * 0.10) if reserve_wh > 0.0 else 50.0
    final_battery = _scalar(sim, "final_battery_Wh")
    battery_margin = _named_margin(constraints, "battery_reserve")
    if battery_margin is None and final_battery is not None and reserve_wh > 0.0:
        battery_margin = final_battery - reserve_wh

    max_speed = float(vehicle.get("max_speed_mps", 30.0))
    max_safe_wind = float(wind_cfg.get("max_safe_wind_mps", max(8.0, max_speed * 0.35)))
    wind_warning_mps = float(wind_cfg.get("warning_margin_mps", 2.0))
    max_wind = _max_horizontal_wind_mps(sim)
    weather_wind = weather.get("wind_gust_mps") or weather.get("wind_speed_mps")
    wind_inputs = [
        float(value)
        for value in (max_wind, weather_wind)
        if value is not None and np.isfinite(float(value))
    ]
    audit_wind = max(wind_inputs) if wind_inputs else None
    wind_margin = None if audit_wind is None else max_safe_wind - audit_wind

    required_clearance = float(geofence_cfg.get("clearance_m", 0.0))
    geofence_margin = _named_margin(constraints, "geofence_clearance")
    geofence_warning_m = max(25.0, required_clearance * 0.25)
    no_entry_margin = _named_margin(constraints, "geofence_no_entry")
    if no_entry_margin is not None and no_entry_margin < 0.0:
        geofence_margin = min(geofence_margin or 0.0, no_entry_margin)

    completed = float(sim.scalars.get("waypoints_completed", 0.0))
    total = float(sim.scalars.get("waypoints_total", 0.0))
    missing = max(0.0, total - completed)
    route_margin = 1.0 if bool(sim.metadata.get("reached_all", False)) else -missing

    turn_margin = _named_margin(constraints, "bank_angle_turn_limit")
    turn_warning = float(vehicle.get("turn_warning_margin_radps", 0.05))

    checks = [
        _check(
            check_id="battery_reserve",
            label="Battery reserve margin",
            margin=battery_margin,
            unit="Wh",
            margin_source=(
                "constraint_result.battery_reserve.min_margin with fallback to "
                "simulation.scalars.final_battery_Wh - vehicle.battery_reserve_Wh"
            ),
            warning_margin=battery_warning_wh,
            warning_margin_source=("max(50 Wh, 10 percent of vehicle.battery_reserve_Wh)"),
            observed={
                "final_battery_Wh": final_battery,
                "required_reserve_Wh": reserve_wh if reserve_wh > 0.0 else None,
            },
            recommendation="Reduce route length or plan a relaunch / battery swap.",
        ),
        _check(
            check_id="wind_weather",
            label="Wind / weather margin",
            margin=wind_margin,
            unit="m/s",
            margin_source=(
                "wind.max_safe_wind_mps minus the larger of simulation wind resources "
                "and weather.resolved wind speed or gust"
            ),
            warning_margin=wind_warning_mps,
            warning_margin_source="wind.warning_margin_mps or default 2.0 m/s",
            observed={
                "max_horizontal_wind_mps": max_wind,
                "weather_audit_wind_mps": audit_wind,
                "max_safe_wind_mps": max_safe_wind,
                "weather_source": weather.get("source"),
                "weather_timestamp_utc": weather.get("timestamp_utc"),
                "weather_wind_speed_mps": weather.get("wind_speed_mps"),
                "weather_wind_direction_deg": weather.get("wind_direction_deg"),
                "weather_wind_gust_mps": weather.get("wind_gust_mps"),
                "visibility_m": weather.get("visibility_m"),
                "precipitation_mm": weather.get("precipitation_mm"),
                "temperature_C": weather.get("temperature_C"),
                "weather_fallback_used": weather.get("fallback_used"),
            },
            recommendation="Wait for better wind or lower mission scope.",
        ),
        _check(
            check_id="geofence_clearance",
            label="Geofence / no-fly-zone clearance",
            margin=geofence_margin,
            unit="m",
            margin_source=(
                "constraint_result.geofence_clearance.min_margin with no-entry violation "
                "override from constraint_result.geofence_no_entry"
            ),
            warning_margin=geofence_warning_m,
            warning_margin_source="max(25 m, 25 percent of geofence.clearance_m)",
            observed={
                "required_clearance_m": required_clearance,
                "min_clearance_m": sim.scalars.get("geofence_min_clearance_m"),
                "geofence_violated": bool(sim.scalars.get("geofence_violated", 0.0)),
            },
            recommendation="Adjust route geometry or increase no-fly-zone clearance.",
        ),
        _check(
            check_id="route_completion",
            label="Route completion status",
            margin=route_margin,
            unit="completion",
            margin_source=(
                "simulation.metadata.reached_all and simulation.scalars waypoint counts"
            ),
            warning_margin=0.5,
            warning_margin_source="fixed 0.5 completion warning band",
            observed={
                "waypoints_completed": completed,
                "waypoints_total": total,
                "reached_all": bool(sim.metadata.get("reached_all", False)),
            },
            recommendation="Split the inspection into shorter sorties.",
        ),
        _check(
            check_id="turn_bank_feasibility",
            label="Turn / bank feasibility",
            margin=turn_margin,
            unit="rad/s",
            margin_source="constraint_result.bank_angle_turn_limit.min_margin",
            warning_margin=turn_warning,
            warning_margin_source=("vehicle.turn_warning_margin_radps or default 0.05 rad/s"),
            observed={"bank_max_deg": vehicle.get("bank_max_deg", None)},
            recommendation="Lower cruise speed or add more turn spacing.",
        ),
    ]

    checks_sorted = sorted(checks, key=lambda item: float(item["risk_points"]), reverse=True)
    top_selection = _top_limiting_constraint_selection(checks_sorted)
    model_transparency = {
        "assumptions_report": _model_assumptions_report(
            plan,
            sim,
            cfg=cfg,
            robustness=robustness,
        ),
        "constraint_margin_sources": [
            {
                "id": check.get("id"),
                "label": check.get("label"),
                "margin_unit": (check.get("margin") or {}).get("unit"),
                "margin_source": (check.get("margin") or {}).get("source"),
                "warning_margin_source": (check.get("warning_margin") or {}).get("source"),
            }
            for check in checks
        ],
        "top_limiting_constraint_selection": top_selection,
        "reproducibility": _reproducibility_report(
            cfg=cfg,
            scenario_path=scenario_path,
            command_used=command_used,
            robustness=robustness,
        ),
        "model_limitations": _model_limitations(cfg, weather),
    }
    hard_pass = bool(getattr(constraints, "hard_pass", False))
    robust_pass_rate = None if not robustness else robustness.get("hard_pass_rate")
    top_points = float(checks_sorted[0]["risk_points"]) if checks_sorted else 0.0
    if (
        (not hard_pass)
        or top_points >= 70.0
        or (robust_pass_rate is not None and float(robust_pass_rate) < 0.95)
    ):
        mission_risk = "high"
    elif top_points >= 35.0 or (robust_pass_rate is not None and float(robust_pass_rate) < 1.0):
        mission_risk = "medium"
    else:
        mission_risk = "low"

    return {
        "kind": "drone_inspection_constraint_audit",
        "primary_demo_artifact": True,
        "operator_question": "Can we safely and defensibly fly this mission?",
        "mission_id": plan.metadata.get("mission_id", "aircraft_mission"),
        "status": "go" if hard_pass else "modify",
        "mission_risk": mission_risk,
        "status_legend": {
            "pass": "Modeled margin is above the configured review threshold.",
            "warning": "Modeled margin is positive, but close enough to require operator review.",
            "fail": "Modeled margin is negative; modify the mission before release.",
            "unknown": "ORBITAL does not have enough data to classify this group.",
        },
        "mission_metadata": mission_metadata,
        "fleet_metadata": fleet_metadata,
        "regulatory_metadata": _regulatory_metadata(cfg),
        "weather_metadata": weather,
        "top_limiting_constraint": checks_sorted[0] if checks_sorted else None,
        "top_limiting_constraint_selection": top_selection,
        "top_three_risk_drivers": checks_sorted[:3],
        "constraint_groups": checks,
        "checks": checks,
        "model_transparency": model_transparency,
        "assumptions_report": model_transparency["assumptions_report"],
        "robustness": robustness or {},
        "summary": {
            "hard_constraints_pass": hard_pass,
            "inspection_points": max(0, len(plan.waypoints or []) - 1),
            "estimated_time_s": _scalar(sim, "t_end_s"),
            "energy_used_Wh": _scalar(sim, "energy_used_Wh"),
        },
    }


def _markdown_cell(value: Any) -> str:
    text = "not provided" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _constraint_status_label(value: Any) -> str:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
    labels = {
        "pass": "PASS",
        "passed": "PASS",
        "warning": "WARNING",
        "review": "WARNING",
        "review_required": "WARNING",
        "fail": "FAIL",
        "failed": "FAIL",
        "unknown": "UNKNOWN",
    }
    return labels.get(normalized, normalized.upper() if normalized else "UNKNOWN")


def _operator_top_limiter_read(top: Dict[str, Any]) -> str:
    if not top:
        return "No top limiting constraint is available for this audit."
    label = str(top.get("label") or "This constraint")
    status = _constraint_status_label(top.get("status"))
    if status == "PASS":
        return (
            f"{label} still passes, but it is the constraint group ORBITAL would "
            "review first because it has the highest modeled risk score."
        )
    if status == "WARNING":
        return (
            f"{label} is still feasible, but it is close enough to the review "
            "threshold that the operator should check assumptions before release."
        )
    if status == "FAIL":
        return (
            f"{label} is failing in the modeled mission; modify the plan before "
            "treating this sortie as release-ready."
        )
    return f"{label} needs operator review because ORBITAL could not classify it cleanly."


def _observed_evidence_summary(observed: Dict[str, Any]) -> str:
    if not observed:
        return "not provided"
    items: List[str] = []
    for key, value in observed.items():
        if len(items) >= 5:
            break
        label = str(key).replace("_", " ")
        if isinstance(value, bool):
            rendered = "yes" if value else "no"
        elif isinstance(value, (int, float)):
            rendered = _fmt_value(value)
        else:
            rendered = str(value)
        items.append(f"{label}: {rendered}")
    remaining = max(0, len(observed) - len(items))
    if remaining:
        items.append(f"{remaining} more fields in the JSON audit")
    return "; ".join(items)


def format_inspection_constraint_audit(audit: Dict[str, Any]) -> str:
    """Render the drone inspection audit payload as Markdown."""
    top = audit.get("top_limiting_constraint") or {}
    transparency = audit.get("model_transparency") or {}
    top_selection = (
        transparency.get("top_limiting_constraint_selection")
        or audit.get("top_limiting_constraint_selection")
        or {}
    )
    regulatory = audit.get("regulatory_metadata") or {}
    weather = audit.get("weather_metadata") or {}
    mission_metadata = audit.get("mission_metadata") or {}
    fleet_metadata = audit.get("fleet_metadata") or {}
    constraint_groups = audit.get("constraint_groups") or audit.get("checks", []) or []

    lines = [
        "# Drone Inspection Constraint Audit",
        "",
        "Primary demo artifact: this report is the operator-facing feasibility case "
        "for the modeled BVLOS inspection mission.",
        "",
        f"Core question: {audit.get('operator_question', 'Can we safely fly this mission?')}",
        "",
        f"Mission: {audit.get('mission_id', 'aircraft_mission')}",
        f"Status: {str(audit.get('status', 'unknown')).upper()}",
        f"Mission risk: {str(audit.get('mission_risk', 'unknown')).upper()}",
        "",
        "## Operator Handoff",
        "",
        "| Signal | Value | How to use it |",
        "| --- | --- | --- |",
        "| Mission status | {status} | First feasibility read from the modeled constraints. |".format(
            status=str(audit.get("status", "unknown")).upper()
        ),
        "| Mission risk | {risk} | Higher risk means the operator should spend more time on the top drivers. |".format(
            risk=str(audit.get("mission_risk", "unknown")).upper()
        ),
        "| Top limiting constraint | {constraint} | Start the detailed review here before changing or releasing the mission. |".format(
            constraint=_markdown_cell(
                "n/a"
                if not top
                else "{label}, {status}, margin {margin} {unit}".format(
                    label=top.get("label", "unknown"),
                    status=_constraint_status_label(top.get("status")),
                    margin=_fmt_value((top.get("margin") or {}).get("value")),
                    unit=(top.get("margin") or {}).get("unit", ""),
                )
            )
        ),
        "",
        "## Status Legend",
        "",
    ]
    legend = audit.get("status_legend") or {}
    for status in ("pass", "warning", "fail", "unknown"):
        meaning = legend.get(status) or _constraint_status_meaning(status)
        lines.append(f"- {status.upper()}: {meaning}")

    lines.extend(
        [
            "",
            "## Top Limiting Constraint",
            "",
            (
                "- n/a"
                if not top
                else "- Constraint: {label}\n- Status: {status}\n- Margin: {margin} {unit}\n- Plain-English read: {read}\n- Why this matters: {why}\n- Operator action: {action}".format(
                    label=top.get("label", "unknown"),
                    status=_constraint_status_label(top.get("status")),
                    margin=_fmt_value((top.get("margin") or {}).get("value")),
                    unit=(top.get("margin") or {}).get("unit", ""),
                    read=_operator_top_limiter_read(top),
                    why=top.get("why_this_matters_to_operator") or "not provided",
                    action=top.get("recommended_operator_action")
                    or top.get("recommendation")
                    or "Review mission plan.",
                )
            ),
            "- Selection detail: "
            f"{top_selection.get('explanation') or 'No selection rationale available.'}",
            "- Selection method: " f"{top_selection.get('method') or 'not provided'}",
            "",
            "## Plain-English Constraint Guide",
            "",
            "| Constraint group | Plain-English read | Operator action |",
            "| --- | --- | --- |",
        ]
    )
    for check in constraint_groups:
        lines.append(
            "| {group} | {read} | {action} |".format(
                group=_markdown_cell(check.get("category_label") or check.get("label")),
                read=_markdown_cell(check.get("plain_english") or "Review this constraint."),
                action=_markdown_cell(
                    check.get("recommended_operator_action")
                    or check.get("recommendation")
                    or "Review mission plan."
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Constraint Group Summary",
            "",
            "| Group | Status | Margin | What ORBITAL checked | Why this matters | Recommended operator action |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for check in constraint_groups:
        margin = check.get("margin") or {}
        margin_text = f"{_fmt_value(margin.get('value'))} {margin.get('unit', '')}".strip()
        lines.append(
            "| {group} | {status} | {margin} | {checked} | {why} | {action} |".format(
                group=_markdown_cell(check.get("category_label") or check.get("label")),
                status=_markdown_cell(_constraint_status_label(check.get("status"))),
                margin=_markdown_cell(margin_text),
                checked=_markdown_cell(check.get("plain_english")),
                why=_markdown_cell(check.get("why_this_matters_to_operator")),
                action=_markdown_cell(
                    check.get("recommended_operator_action")
                    or check.get("recommendation")
                    or "Review mission plan."
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Model Transparency",
            "",
            "### Assumptions Report",
            "",
        ]
    )
    for item in transparency.get("assumptions_report", []) or []:
        lines.extend(
            [
                f"#### {item.get('label') or item.get('id') or 'Assumption'}",
                "",
                f"- Source: {item.get('source') or 'not provided'}",
                f"- Assumption: {item.get('assumption') or 'not provided'}",
                "- Operator review note: " f"{item.get('operator_review_note') or 'not provided'}",
                "",
                "| Input | Value | Unit | Source |",
                "| --- | ---: | --- | --- |",
            ]
        )
        for field in item.get("inputs", []) or []:
            lines.append(
                "| {name} | {value} | {unit} | {source} |".format(
                    name=_markdown_cell(field.get("name")),
                    value=_markdown_cell(field.get("value")),
                    unit=_markdown_cell(field.get("unit")),
                    source=_markdown_cell(field.get("source")),
                )
            )
        lines.append("")

    lines.extend(
        [
            "### Constraint Margin Units And Sources",
            "",
            "| Constraint | Unit | Margin source | Warning margin source |",
            "| --- | --- | --- | --- |",
        ]
    )
    for check in constraint_groups:
        margin = check.get("margin") or {}
        warning_margin = check.get("warning_margin") or {}
        lines.append(
            "| {label} | {unit} | {source} | {warning_source} |".format(
                label=_markdown_cell(check.get("label")),
                unit=_markdown_cell(margin.get("unit")),
                source=_markdown_cell(margin.get("source")),
                warning_source=_markdown_cell(warning_margin.get("source")),
            )
        )

    reproducibility = transparency.get("reproducibility") or {}
    command = reproducibility.get("command") or {}
    lines.extend(
        [
            "",
            "### Reproducibility",
            "",
            f"- Scenario path: {reproducibility.get('scenario_path') or 'not provided'}",
            f"- Seed: {reproducibility.get('seed') if reproducibility.get('seed') is not None else 'not provided'}",
            "- Iterations: "
            f"{reproducibility.get('iterations') if reproducibility.get('iterations') is not None else 'not provided'}",
            f"- Restarts: {reproducibility.get('restarts') if reproducibility.get('restarts') is not None else 'not provided'}",
            "- Robustness cases configured: "
            f"{reproducibility.get('robustness_cases_configured')}",
            "- Robustness cases run: " f"{reproducibility.get('robustness_cases_run')}",
            f"- Command: {command.get('display') or 'not provided'}",
            f"- ORBITAL version: {reproducibility.get('orbital_version') or 'not provided'}",
            "",
            "### Model Limitations",
            "",
        ]
    )
    for limitation in transparency.get("model_limitations", []) or []:
        applies = "applies" if limitation.get("applies") else "context"
        lines.append(f"- {applies}: {limitation.get('limitation') or 'not provided'}")

    lines.extend(
        [
            "",
            "## Mission / Fleet Metadata",
            "",
            f"- Operator: {mission_metadata.get('operator') or 'not provided'}",
            f"- Aircraft ID: {mission_metadata.get('aircraft_id') or 'not provided'}",
            f"- Pilot: {mission_metadata.get('pilot') or 'not provided'}",
            f"- Organization: {mission_metadata.get('organization') or 'not provided'}",
            f"- Asset owner: {mission_metadata.get('asset_owner') or 'not provided'}",
            f"- Drone model: {fleet_metadata.get('drone_model') or 'not provided'}",
            f"- Battery pack ID: {fleet_metadata.get('battery_pack_id') or 'not provided'}",
            f"- Sensor payload: {fleet_metadata.get('sensor_payload') or 'not provided'}",
            f"- Inspection type: {fleet_metadata.get('inspection_type') or 'not provided'}",
            "",
            "## Regulatory Metadata",
            "",
            f"- LAANC required: {_yes_no_unknown(regulatory.get('laanc_required'))}",
            "- Waiver / authorization required: "
            f"{_yes_no_unknown(regulatory.get('waiver_or_authorization_required'))}",
            f"- Airspace class: {regulatory.get('airspace_class') or 'unknown'}",
            f"- Visual observer required: "
            f"{_yes_no_unknown(regulatory.get('visual_observer_required'))}",
            "- Ground-risk / population note: "
            f"{regulatory.get('ground_risk_population_note') or 'not provided'}",
            f"- Documentation-only notice: {regulatory.get('documentation_only_notice')}",
            "",
            "## Weather Metadata",
            "",
            f"- Source: {weather.get('source') or 'not provided'}",
            f"- Provider: {weather.get('provider') or 'not provided'}",
            f"- Timestamp: {weather.get('timestamp_utc') or 'not provided'}",
            f"- Location: {weather.get('location_name') or 'not provided'}",
            f"- Forecast window start: "
            f"{weather.get('forecast_window_start_utc') or 'not provided'}",
            f"- Forecast window hours: {_fmt_value(weather.get('forecast_window_hours'))}",
            f"- Wind speed: {_fmt_value(weather.get('wind_speed_mps'), 'm/s')}",
            f"- Wind direction: {_fmt_value(weather.get('wind_direction_deg'), 'deg')}",
            f"- Wind gust: {_fmt_value(weather.get('wind_gust_mps'), 'm/s')}",
            f"- Visibility: {_fmt_value(weather.get('visibility_m'), 'm')}",
            f"- Precipitation: {_fmt_value(weather.get('precipitation_mm'), 'mm')}",
            f"- Temperature: {_fmt_value(weather.get('temperature_C'), 'C')}",
            f"- Fallback used: {_yes_no_unknown(weather.get('fallback_used'))}",
            "",
            "## Top Three Risk Drivers",
            "",
        ]
    )
    for driver in audit.get("top_three_risk_drivers", []) or []:
        margin = driver.get("margin") or {}
        lines.append(
            "- {label}: {status}, margin {value} {unit}, risk points {points}".format(
                label=driver.get("label", "unknown"),
                status=str(driver.get("status", "unknown")).upper(),
                value=_fmt_value(margin.get("value")),
                unit=margin.get("unit", ""),
                points=_fmt_value(driver.get("risk_points")),
            )
        )

    lines.extend(["", "## Detailed Operator Review", ""])
    for check in constraint_groups:
        margin = check.get("margin") or {}
        observed = check.get("observed") or {}
        lines.extend(
            [
                f"### {check.get('label', 'Constraint')}",
                "",
                f"- Group: {check.get('category_label') or check.get('category') or 'not provided'}",
                f"- What this checks: {check.get('plain_english') or 'Not provided.'}",
                "- Why this matters to an operator: "
                f"{check.get('why_this_matters_to_operator') or 'Not provided.'}",
                f"- Status: {_constraint_status_label(check.get('status'))}",
                f"- Status meaning: {check.get('status_meaning') or 'Not provided.'}",
                f"- Margin: {_fmt_value(margin.get('value'))} {margin.get('unit', '')}",
                f"- Warning margin: "
                f"{_fmt_value((check.get('warning_margin') or {}).get('value'))} "
                f"{(check.get('warning_margin') or {}).get('unit', '')}",
                f"- Observed evidence: {_observed_evidence_summary(observed)}",
                "- Recommended operator action: "
                f"{check.get('recommended_operator_action') or check.get('recommendation') or 'Review mission plan.'}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def export_inspection_constraint_audit(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    out_dir: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
    scenario_path: Optional[Any] = None,
    command_used: Optional[Any] = None,
) -> Dict[str, Any]:
    """Write drone inspection audit JSON and Markdown artifacts."""
    audit = build_inspection_constraint_audit(
        plan,
        sim,
        constraints,
        cfg=cfg,
        robustness=robustness,
        scenario_path=scenario_path,
        command_used=command_used,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_strict_json(out_dir / "inspection_constraint_audit.json", audit)
    (out_dir / "inspection_constraint_audit.md").write_text(
        format_inspection_constraint_audit(audit),
        encoding="utf-8",
    )
    return audit


def _regulatory_summary_item(
    *,
    key: str,
    label: str,
    value: Any,
    yes_summary: str,
    no_summary: str,
    unknown_summary: str,
) -> Dict[str, Any]:
    if value is None:
        summary = unknown_summary
    elif bool(value):
        summary = yes_summary
    else:
        summary = no_summary
    if value is None:
        status = "unknown"
    elif bool(value):
        status = "required"
    else:
        status = "not_required_as_configured"
    return {
        "id": key,
        "label": label,
        "value": value,
        "configured": value,
        "status": status,
        "summary": summary,
    }


def _regulatory_readiness_state(regulatory: Dict[str, Any]) -> str:
    required_or_unknown = (
        regulatory.get("laanc_required") is not False
        or regulatory.get("waiver_or_authorization_required") is not False
        or regulatory.get("visual_observer_required") is not False
        or not regulatory.get("airspace_class")
        or not regulatory.get("ground_risk_population_note")
    )
    if required_or_unknown:
        return "operator_action_required"
    return "documented_review_required"


def _regulatory_operating_assumptions(regulatory: Dict[str, Any]) -> List[str]:
    configured = list(regulatory.get("operating_assumptions") or [])
    if configured:
        return configured

    airspace = regulatory.get("airspace_class") or "unknown airspace class"
    ground_note = regulatory.get("ground_risk_population_note") or "not provided"
    assumptions = [
        "Regulatory fields are scenario-provided documentation inputs; ORBITAL does not "
        "query or validate official FAA, LAANC, UTM, NOTAM, TFR, or local authority systems.",
        f"The mission is treated as operating in {airspace} for planning context only.",
        "Route, battery, weather, geofence, and constraint results support operator review, "
        "not regulatory clearance.",
        f"Ground-risk / population context is operator-provided: {ground_note}",
        "The pilot-in-command and operator remain responsible for final mission release, "
        "crew readiness, site permissions, and all required approvals.",
    ]
    if regulatory.get("visual_observer_required") is True:
        assumptions.append(
            "The scenario assumes visual observer support is required; ORBITAL does not "
            "verify observer placement, communications, or staffing."
        )
    return assumptions


def _regulatory_unresolved_items(regulatory: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = [
        {
            "id": f"operator_provided_item_{idx}",
            "label": "Operator-provided unresolved item",
            "status": "operator_action_required",
            "note": item,
        }
        for idx, item in enumerate(regulatory.get("unresolved_items") or [], start=1)
    ]
    if regulatory.get("laanc_required") is True:
        items.append(
            {
                "id": "laanc_authorization_confirmation",
                "label": "LAANC / airspace authorization confirmation",
                "status": "operator_action_required",
                "note": "Scenario indicates LAANC is required; authorization evidence must be obtained and checked outside ORBITAL before flight.",
            }
        )
    elif regulatory.get("laanc_required") is None:
        items.append(
            {
                "id": "laanc_required_status_unknown",
                "label": "LAANC required status",
                "status": "incomplete",
                "note": "Scenario does not state whether LAANC is required.",
            }
        )

    if regulatory.get("waiver_or_authorization_required") is True:
        items.append(
            {
                "id": "waiver_or_authorization_confirmation",
                "label": "Waiver / authorization confirmation",
                "status": "operator_action_required",
                "note": "Scenario indicates a waiver or authorization is required; document ID, scope, dates, and operating conditions remain outside ORBITAL.",
            }
        )
    elif regulatory.get("waiver_or_authorization_required") is None:
        items.append(
            {
                "id": "waiver_or_authorization_status_unknown",
                "label": "Waiver / authorization required status",
                "status": "incomplete",
                "note": "Scenario does not state whether a waiver or authorization is required.",
            }
        )

    if not regulatory.get("airspace_class"):
        items.append(
            {
                "id": "airspace_class_missing",
                "label": "Airspace class",
                "status": "incomplete",
                "note": "Scenario does not provide an airspace class for planning documentation.",
            }
        )

    if regulatory.get("visual_observer_required") is True:
        items.append(
            {
                "id": "visual_observer_staffing_plan",
                "label": "Visual observer staffing plan",
                "status": "operator_action_required",
                "note": "Scenario indicates a visual observer is required; crew assignment, placement, and communications plan must be confirmed by the operator.",
            }
        )
    elif regulatory.get("visual_observer_required") is None:
        items.append(
            {
                "id": "visual_observer_status_unknown",
                "label": "Visual observer requirement",
                "status": "incomplete",
                "note": "Scenario does not state whether visual observer support is required.",
            }
        )

    if not regulatory.get("ground_risk_population_note"):
        items.append(
            {
                "id": "ground_risk_population_note_missing",
                "label": "Ground-risk / population note",
                "status": "incomplete",
                "note": "Scenario does not include a ground-risk or population context note.",
            }
        )

    items.extend(
        [
            {
                "id": "current_airspace_status",
                "label": "Current airspace, NOTAM/TFR, and local restrictions",
                "status": "operator_action_required",
                "note": "Current restrictions, UAS facility map limits, site permissions, and local rules must be checked outside ORBITAL close to flight time.",
            },
            {
                "id": "pic_final_acceptance",
                "label": "Pilot-in-command final acceptance",
                "status": "operator_action_required",
                "note": "Final operational approval, crew briefing, and go/no-go authority remain with the pilot-in-command and operator.",
            },
        ]
    )
    return items


def _regulatory_evidence_fields(regulatory: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "documentation_only": True,
        "authorization_id": regulatory.get("authorization_id"),
        "authorization_authority": regulatory.get("authorization_authority"),
        "approving_authority_source": regulatory.get("approving_authority_source"),
        "authorization_date_checked_utc": regulatory.get("authorization_date_checked_utc"),
        "authorization_expiration_date": regulatory.get("authorization_expiration_date"),
        "operator_confirmation_status": regulatory.get("operator_confirmation_status"),
        "operating_altitude_limit_m": regulatory.get("operating_altitude_limit_m"),
        "operating_time_window": regulatory.get("operating_time_window") or {},
        "required_crew_roles": list(regulatory.get("required_crew_roles") or []),
        "special_conditions_limitations": list(
            regulatory.get("special_conditions_limitations") or []
        ),
        "emergency_contingency_plan": regulatory.get("emergency_contingency_plan"),
        "notice": (
            "Optional documentation-only evidence fields. ORBITAL records these values "
            "for operator review but does not verify, approve, or issue authorizations."
        ),
    }


def _documentation_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_documentation_value_present(item) for item in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict, str)):
        return any(_documentation_value_present(item) for item in value)
    return True


def _regulatory_evidence_status(
    regulatory: Dict[str, Any], evidence: Dict[str, Any]
) -> Dict[str, Any]:
    authorization_needed = (
        regulatory.get("laanc_required") is True
        or regulatory.get("waiver_or_authorization_required") is True
    )
    visual_observer_needed = regulatory.get("visual_observer_required") is True
    time_window = evidence.get("operating_time_window")
    if not isinstance(time_window, dict):
        time_window = {}
    time_window_present = _documentation_value_present(
        time_window.get("start_utc")
    ) and _documentation_value_present(time_window.get("end_utc"))

    field_specs = [
        {
            "id": "authorization_id",
            "label": "Authorization ID / reference number",
            "path": "regulatory.authorization_id",
            "present": _documentation_value_present(evidence.get("authorization_id")),
            "recommended_when": "LAANC or waiver / authorization is required.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "approving_authority_source",
            "label": "Approving authority / source",
            "path": "regulatory.approving_authority_source",
            "present": _documentation_value_present(evidence.get("approving_authority_source")),
            "recommended_when": "Authorization evidence is referenced.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "authorization_authority",
            "label": "Authorization authority",
            "path": "regulatory.authorization_authority",
            "present": _documentation_value_present(evidence.get("authorization_authority")),
            "recommended_when": "Authorization evidence is referenced.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "authorization_date_checked_utc",
            "label": "Authorization date checked",
            "path": "regulatory.authorization_date_checked_utc",
            "present": _documentation_value_present(evidence.get("authorization_date_checked_utc")),
            "recommended_when": "Authorization evidence is referenced.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "authorization_expiration_date",
            "label": "Authorization expiration date",
            "path": "regulatory.authorization_expiration_date",
            "present": _documentation_value_present(evidence.get("authorization_expiration_date")),
            "recommended_when": "Authorization evidence is referenced.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "operator_confirmation_status",
            "label": "Operator confirmation status",
            "path": "regulatory.operator_confirmation_status",
            "present": _documentation_value_present(evidence.get("operator_confirmation_status")),
            "recommended_when": "Authorization evidence is referenced.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "operating_altitude_limit_m",
            "label": "Operating altitude limit",
            "path": "regulatory.operating_altitude_limit_m",
            "present": _documentation_value_present(evidence.get("operating_altitude_limit_m")),
            "recommended_when": "An authorization or operational limit applies.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "operating_time_window",
            "label": "Operating time window",
            "path": "regulatory.operating_time_window",
            "present": time_window_present,
            "recommended_when": "An authorization or time-bounded operation applies.",
            "operator_attention_when_missing": authorization_needed,
        },
        {
            "id": "required_crew_roles",
            "label": "Required crew roles",
            "path": "regulatory.required_crew_roles",
            "present": _documentation_value_present(evidence.get("required_crew_roles")),
            "recommended_when": "Crew-role constraints or visual observer support apply.",
            "operator_attention_when_missing": visual_observer_needed,
        },
        {
            "id": "special_conditions_limitations",
            "label": "Special conditions / limitations",
            "path": "regulatory.special_conditions_limitations",
            "present": _documentation_value_present(evidence.get("special_conditions_limitations")),
            "recommended_when": "An authorization includes special conditions.",
            "operator_attention_when_missing": False,
        },
        {
            "id": "emergency_contingency_plan",
            "label": "Emergency / contingency plan documentation",
            "path": "regulatory.emergency_contingency_plan",
            "present": _documentation_value_present(evidence.get("emergency_contingency_plan")),
            "recommended_when": "BVLOS, authorization-bound, or higher-risk operations are planned.",
            "operator_attention_when_missing": authorization_needed or visual_observer_needed,
        },
    ]

    fields: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    operator_attention_missing: List[Dict[str, Any]] = []
    for spec in field_specs:
        present = bool(spec["present"])
        entry = {
            "id": spec["id"],
            "label": spec["label"],
            "path": spec["path"],
            "present": present,
            "documentation_only": True,
            "recommended_when": spec["recommended_when"],
            "operator_attention_when_missing": bool(spec["operator_attention_when_missing"]),
        }
        fields.append(entry)
        if not present:
            missing_entry = {
                "id": entry["id"],
                "label": entry["label"],
                "path": entry["path"],
                "documentation_only": True,
                "recommended_when": entry["recommended_when"],
                "operator_attention": entry["operator_attention_when_missing"],
                "note": (
                    "Documentation-only field is not supplied; this is visible for "
                    "operator review and does not block planning by itself."
                ),
            }
            missing.append(missing_entry)
            if missing_entry["operator_attention"]:
                operator_attention_missing.append(missing_entry)

    return {
        "documentation_only": True,
        "all_optional_fields_documented": not missing,
        "field_count": len(fields),
        "missing_count": len(missing),
        "operator_attention_missing_count": len(operator_attention_missing),
        "fields": fields,
        "missing": missing,
        "operator_attention_missing": operator_attention_missing,
        "notice": (
            "Regulatory evidence fields are optional documentation. Missing fields are "
            "reported for operator review but do not make ORBITAL an approval system "
            "or block planning by themselves."
        ),
    }


def _read_json_mapping(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_generated_timestamp(value: Optional[Any] = None) -> str:
    """Return a normalized UTC timestamp for generated demo artifacts."""
    if value is None or str(value).strip() == "":
        return _utc_now_iso()
    parsed = _parse_utc_datetime(value)
    if parsed is None:
        raise ValueError(
            "generated timestamp must be an ISO-8601 UTC timestamp, for example "
            "2026-09-15T05:24:50Z"
        )
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_from_timestamp(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _file_sha256(path: Path) -> Optional[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


def _file_size(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _file_modified_utc(path: Path) -> Optional[str]:
    try:
        return _utc_from_timestamp(path.stat().st_mtime)
    except OSError:
        return None


def _file_modified_timestamp(path: Path) -> Optional[float]:
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return None


def _generated_timestamp_epoch(generated_timestamp_utc: str) -> Optional[float]:
    parsed = _parse_utc_datetime(generated_timestamp_utc)
    return None if parsed is None else parsed.timestamp()


def _touch_generated_file(path: Path, generated_timestamp_utc: str) -> None:
    timestamp = _generated_timestamp_epoch(generated_timestamp_utc)
    if timestamp is None:
        return
    try:
        os.utime(path, (timestamp, timestamp))
    except OSError:
        return


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _orbital_version() -> str:
    try:
        from mission_framework import __version__ as package_version

        if package_version:
            return str(package_version)
    except Exception:
        pass
    try:
        return version("orbital-mission-framework")
    except PackageNotFoundError:
        return "unknown"


def _command_metadata(command_used: Optional[Any]) -> Dict[str, Any]:
    if isinstance(command_used, dict):
        argv = command_used.get("argv")
        display = command_used.get("display")
        if isinstance(argv, (list, tuple)):
            normalized_argv = _normalize_command_argv(argv)
            display_text = (
                subprocess.list2cmdline(normalized_argv)
                if normalized_argv
                else str(display).strip() if display else "not provided"
            )
            return {
                "display": display_text,
                "argv": normalized_argv,
            }
        return {
            "display": str(display).strip() if display else "not provided",
            "argv": [],
        }
    if isinstance(command_used, (list, tuple)):
        argv = _normalize_command_argv(command_used)
        return {
            "display": subprocess.list2cmdline(argv) if argv else "not provided",
            "argv": argv,
        }
    if command_used:
        return {"display": str(command_used), "argv": []}
    return {"display": "not provided", "argv": []}


def _normalize_command_argv(argv: Iterable[Any]) -> List[str]:
    normalized = [str(item) for item in argv]
    if normalized and _is_python_executable(normalized[0]):
        normalized[0] = "python"
    return normalized


def _is_python_executable(token: str) -> bool:
    candidates = {
        Path(token).name.lower(),
        PureWindowsPath(token).name.lower(),
    }
    python_names = {
        "python",
        "python.exe",
        "python3",
        "python3.exe",
        "py",
        "py.exe",
    }
    return any(candidate in python_names for candidate in candidates)


def _portable_path_text(path: Path, *, base_dir: Optional[Path] = None) -> str:
    """Return a stable display path when the file sits under the working tree."""
    base = base_dir or Path.cwd()
    try:
        return str(Path(path).resolve().relative_to(base.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


def _regulatory_documentation_completeness(
    regulatory_evidence_status: Dict[str, Any],
) -> Dict[str, Any]:
    field_count = int(regulatory_evidence_status.get("field_count", 0) or 0)
    missing_count = int(regulatory_evidence_status.get("missing_count", 0) or 0)
    documented = max(0, field_count - missing_count)
    score = 100.0 if field_count == 0 else round((documented / field_count) * 100.0, 1)
    return {
        "score": score,
        "unit": "percent",
        "documented_fields": documented,
        "total_fields": field_count,
        "missing_fields": missing_count,
        "operator_attention_missing_fields": int(
            regulatory_evidence_status.get("operator_attention_missing_count", 0) or 0
        ),
        "complete": missing_count == 0,
        "documentation_only": True,
        "scoring_note": (
            "Score is based on optional regulatory documentation fields. Missing fields "
            "are visible for operator review but do not block planning or imply approval."
        ),
    }


def _artifact_freshness_metadata(
    *,
    source: Path,
    destination: Path,
    present: bool,
    scenario_modified_ts: Optional[float],
) -> Dict[str, Any]:
    source_modified_ts = _file_modified_timestamp(source) if present else None
    stale = False
    if (
        present
        and scenario_modified_ts is not None
        and source_modified_ts is not None
        and source.name != "scenario.yaml"
    ):
        stale = source_modified_ts < scenario_modified_ts
    return {
        "source_sha256": _file_sha256(source) if present else None,
        "bundle_sha256": _file_sha256(destination) if destination.exists() else None,
        "source_modified_utc": _file_modified_utc(source) if present else None,
        "bundle_modified_utc": _file_modified_utc(destination) if destination.exists() else None,
        "source_size_bytes": _file_size(source) if present else None,
        "bundle_size_bytes": _file_size(destination) if destination.exists() else None,
        "stale_against_scenario": stale,
    }


def _bundle_warnings(
    manifest_entries: List[Dict[str, Any]],
    *,
    scenario_sha256: Optional[str],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for entry in manifest_entries:
        if not entry.get("present"):
            warnings.append(
                {
                    "id": f"missing_{entry.get('id')}",
                    "kind": "missing_artifact",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "label": entry.get("label"),
                    "bundle_path": entry.get("bundle_path"),
                    "message": "Expected evidence artifact is missing from the bundle.",
                }
            )
        freshness = entry.get("freshness") or {}
        if freshness.get("stale_against_scenario"):
            warnings.append(
                {
                    "id": f"stale_{entry.get('id')}",
                    "kind": "stale_artifact",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "label": entry.get("label"),
                    "bundle_path": entry.get("bundle_path"),
                    "message": (
                        "Artifact source appears older than the scenario file used for "
                        "the evidence bundle."
                    ),
                }
            )
    scenario_entry = next(
        (entry for entry in manifest_entries if entry.get("id") == "scenario_yaml"),
        None,
    )
    scenario_bundle_hash = (
        (scenario_entry.get("freshness") or {}).get("bundle_sha256")
        if scenario_entry is not None
        else None
    )
    if scenario_sha256 and scenario_bundle_hash and scenario_sha256 != scenario_bundle_hash:
        warnings.append(
            {
                "id": "scenario_hash_mismatch",
                "kind": "scenario_metadata_mismatch",
                "severity": "warning",
                "artifact_id": "scenario_yaml",
                "bundle_path": "scenario.yaml",
                "message": (
                    "Bundled scenario.yaml does not match the scenario hash recorded in "
                    "manifest freshness metadata."
                ),
            }
        )
    return warnings


def _operational_evidence_warnings(
    *,
    weather_readiness: Dict[str, Any],
    regulatory_provenance: Dict[str, Any],
    manifest_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    weather_status = str(weather_readiness.get("status") or "").upper()
    if weather_status in {"MISSING", "STALE", "SAMPLE", "FALLBACK USED"}:
        severity = "warning" if weather_status in {"MISSING", "STALE"} else "review"
        warnings.append(
            {
                "id": f"weather_evidence_{weather_status.lower().replace(' ', '_')}",
                "kind": "weather_evidence",
                "severity": severity,
                "message": weather_readiness.get("operator_action")
                or "Review weather evidence before operator release.",
                "source": weather_readiness.get("source"),
                "timestamp_utc": weather_readiness.get("timestamp_utc"),
                "freshness_status": weather_readiness.get("freshness_status"),
                "documentation_only": True,
            }
        )

    regulatory_status = str(regulatory_provenance.get("status") or "").upper()
    if regulatory_status in {
        "MISSING",
        "STALE",
        "EXPIRED",
        "PENDING OPERATOR CONFIRMATION",
    }:
        warnings.append(
            {
                "id": f"regulatory_provenance_{regulatory_status.lower().replace(' ', '_')}",
                "kind": "regulatory_evidence_provenance",
                "severity": "warning",
                "message": regulatory_provenance.get("operator_action")
                or "Review regulatory evidence provenance before operator release.",
                "source": regulatory_provenance.get("source"),
                "date_checked_utc": regulatory_provenance.get("date_checked_utc"),
                "expiration_date": regulatory_provenance.get("expiration_date"),
                "authority": regulatory_provenance.get("authority"),
                "documentation_only": True,
            }
        )

    route_export_ids = {
        "autopilot_mission_csv",
        "mission_review_kml",
        "flight_planning_exports_manifest",
        "flight_planning_exports_readme",
    }
    for entry in manifest_entries:
        if entry.get("id") not in route_export_ids:
            continue
        freshness = entry.get("freshness") or {}
        if not entry.get("present"):
            warnings.append(
                {
                    "id": f"route_export_missing_{entry.get('id')}",
                    "kind": "route_export_missing",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "bundle_path": entry.get("bundle_path"),
                    "message": (
                        "Route/export artifact is missing; regenerate exports before "
                        "field or autopilot review."
                    ),
                }
            )
        elif freshness.get("stale_against_scenario"):
            warnings.append(
                {
                    "id": f"route_export_stale_{entry.get('id')}",
                    "kind": "route_export_stale",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "bundle_path": entry.get("bundle_path"),
                    "message": (
                        "Route/export artifact appears older than the scenario; regenerate "
                        "exports before field or autopilot review."
                    ),
                }
            )

    checksum_entry = next(
        (entry for entry in manifest_entries if entry.get("id") == "checksum_manifest"),
        None,
    )
    if checksum_entry is not None and not checksum_entry.get("present"):
        warnings.append(
            {
                "id": "checksum_manifest_missing",
                "kind": "checksum_evidence",
                "severity": "warning",
                "bundle_path": "checksum_manifest.json",
                "message": "Checksum manifest is missing; archive verification is unavailable.",
            }
        )
    return warnings


def _checksum_evidence_readiness(generated_timestamp_utc: str) -> Dict[str, Any]:
    return {
        "documentation_only": True,
        "status": "VERIFY REQUIRED",
        "bundle_path": "checksum_manifest.json",
        "generated_timestamp_utc": generated_timestamp_utc,
        "operator_action": (
            "Run bundle checksum verification after generation and before archiving or "
            "sharing the evidence bundle."
        ),
        "summary": (
            "Checksum manifest is generated with the bundle; verification must be run "
            "against the final archived files."
        ),
        "notice": (
            "Checksums support file integrity review only. They do not approve a mission "
            "or verify regulatory authorization."
        ),
    }


def _percent_text(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return "n/a"
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return _fmt_value(number, "%")


def _weather_fallback_summary(weather: Dict[str, Any]) -> Dict[str, Any]:
    if not weather:
        return {
            "status": "UNKNOWN",
            "summary": "No weather metadata was captured in the evidence bundle.",
            "operator_action": "Confirm current field weather before release.",
        }
    fallback_used = weather.get("fallback_used")
    if fallback_used is True:
        status = "FALLBACK USED"
        operator_action = "Refresh current field weather and keep the source with the bundle."
    elif fallback_used is False:
        status = "CONFIGURED SOURCE"
        operator_action = "Confirm the weather timestamp is still valid for the operating window."
    else:
        status = "UNKNOWN"
        operator_action = "Confirm weather source, timestamp, and field conditions before release."
    source = weather.get("source") or "not provided"
    timestamp = weather.get("timestamp_utc") or "not provided"
    reason = weather.get("fallback_reason")
    summary = f"{status}: source {source}, timestamp {timestamp}"
    if reason:
        summary = f"{summary}, reason {reason}"
    return {
        "status": status,
        "summary": summary,
        "source": source,
        "provider": weather.get("provider") or "not provided",
        "timestamp_utc": timestamp,
        "fallback_used": fallback_used,
        "fallback_reason": reason,
        "live_fetch_enabled": weather.get("live_fetch_enabled"),
        "applied_to_wind": weather.get("applied_to_wind"),
        "operator_action": operator_action,
    }


def _robustness_summary(robustness: Dict[str, Any]) -> Dict[str, Any]:
    cases = int(robustness.get("cases", 0) or 0) if robustness else 0
    pass_rate = _float_or_none(robustness.get("hard_pass_rate")) if robustness else None
    worst_margin = _float_or_none(robustness.get("worst_hard_margin_min")) if robustness else None
    if cases <= 0:
        return {
            "status": "NOT RUN",
            "summary": (
                "No robustness cases were recorded for this bundle. Confidence from "
                "uncertainty testing is not estimated."
            ),
            "operator_action": "Run robustness cases when uncertainty or margin sensitivity matters.",
            "confidence": "not estimated",
            "cases": cases,
            "hard_pass_rate": pass_rate,
            "worst_hard_margin_min": worst_margin,
        }
    if pass_rate is None:
        status = "REVIEW"
    elif pass_rate >= 1.0:
        status = "PASS"
    elif pass_rate >= 0.95:
        status = "REVIEW"
    else:
        status = "ELEVATED RISK"
    return {
        "status": status,
        "summary": (
            f"{status}: {cases} case(s), hard pass rate {_percent_text(pass_rate)}, "
            f"worst hard margin {_fmt_value(worst_margin)}. Confidence from configured "
            "robustness cases is scenario-limited and should be reviewed against "
            "operator uncertainty assumptions."
        ),
        "operator_action": (
            "Review robustness assumptions and rerun with scenario-specific uncertainty "
            "ranges if margins are close."
        ),
        "confidence": (
            "configured-case confidence" if status == "PASS" else "review uncertainty assumptions"
        ),
        "cases": cases,
        "hard_pass_rate": pass_rate,
        "worst_hard_margin_min": worst_margin,
        "aggregation": robustness.get("robust_aggregation"),
        "cvar_alpha": robustness.get("cvar_alpha"),
    }


def _sample_data_demo_note(
    *,
    scenario_path: Path,
    mission_id: Any,
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    path_text = str(scenario_path).replace("\\", "/").lower()
    mission_text = str(mission_id or "").lower()
    source_text = str(weather.get("source") or "").lower()
    is_demo = (
        "demo" in path_text
        or "sample" in path_text
        or "demo" in mission_text
        or "offline" in source_text
        or "sample" in source_text
    )
    if is_demo:
        note = (
            "Sample data / demo scenario: this bundle uses demonstration planning inputs, "
            "including offline or sample weather where configured. Replace route, weather, "
            "regulatory, crew, and customer evidence before operational use. Operator "
            "should verify sample data outside ORBITAL."
        )
    else:
        note = (
            "Scenario data note: verify route, weather, regulatory, crew, and customer "
            "evidence before operational use. Operator should verify source inputs."
        )
    return {"is_demo_or_sample": is_demo, "note": note}


def _trust_defensibility_summary(
    *,
    constraint_audit: Dict[str, Any],
    manifest_entries: List[Dict[str, Any]],
    missing_evidence: List[Dict[str, Any]],
    bundle_warnings: List[Dict[str, Any]],
    weather: Dict[str, Any],
    weather_readiness: Optional[Dict[str, Any]] = None,
    regulatory_provenance: Optional[Dict[str, Any]] = None,
    scenario_path: Path,
) -> Dict[str, Any]:
    transparency = constraint_audit.get("model_transparency") or {}
    assumptions = []
    for item in transparency.get("assumptions_report", []) or []:
        assumptions.append(
            {
                "id": item.get("id"),
                "label": item.get("label") or item.get("id") or "Model assumption",
                "assumption": item.get("assumption") or "not provided",
                "operator_review_note": item.get("operator_review_note")
                or "Review before release.",
            }
        )
    limitations = []
    for item in transparency.get("model_limitations", []) or []:
        limitations.append(
            {
                "id": item.get("id"),
                "applies": bool(item.get("applies")),
                "limitation": item.get("limitation") or "not provided",
            }
        )
    stale_artifacts = [
        {
            "id": entry.get("id"),
            "label": entry.get("label"),
            "bundle_path": entry.get("bundle_path"),
        }
        for entry in manifest_entries
        if (entry.get("freshness") or {}).get("stale_against_scenario")
    ]
    missing_artifacts = [
        {
            "id": entry.get("id"),
            "label": entry.get("label"),
            "bundle_path": entry.get("bundle_path"),
        }
        for entry in manifest_entries
        if not entry.get("present")
    ]
    warning_status = (
        "CLEAR"
        if not missing_artifacts
        and not stale_artifacts
        and not missing_evidence
        and not bundle_warnings
        else "REVIEW REQUIRED"
    )
    return {
        "sample_data_demo_note": _sample_data_demo_note(
            scenario_path=scenario_path,
            mission_id=constraint_audit.get("mission_id"),
            weather=weather,
        ),
        "model_assumptions_summary": assumptions,
        "known_limitations_summary": limitations,
        "weather_fallback_status": weather_readiness or _weather_fallback_summary(weather),
        "weather_evidence_readiness": weather_readiness
        or _weather_evidence_readiness(weather, generated_timestamp_utc=_utc_now_iso()),
        "regulatory_evidence_provenance": regulatory_provenance or {},
        "uncertainty_robustness_status": _robustness_summary(
            constraint_audit.get("robustness") or {}
        ),
        "evidence_warning_summary": {
            "status": warning_status,
            "missing_artifacts": len(missing_artifacts),
            "stale_artifacts": len(stale_artifacts),
            "missing_evidence": len(missing_evidence),
            "bundle_warnings": len(bundle_warnings),
            "summary": (
                f"{warning_status}: {len(missing_artifacts)} missing artifact(s), "
                f"{len(stale_artifacts)} stale artifact(s), "
                f"{len(missing_evidence)} missing evidence item(s), "
                f"{len(bundle_warnings)} bundle warning(s)"
            ),
            "stale_artifacts_detail": stale_artifacts,
            "missing_artifacts_detail": missing_artifacts,
        },
    }


def _approval_checklist_summary(
    readiness_report: Dict[str, Any],
    *,
    regulatory: Dict[str, Any],
    cfg: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    checklist = readiness_report.get("operator_approval_checklist")
    source_artifact = "regulatory_readiness_report.json"
    if not isinstance(checklist, list):
        checklist = _operator_approval_checklist(
            regulatory=regulatory,
            cfg=cfg,
            sim=None,
            constraints=None,
        )
        source_artifact = "scenario regulatory metadata"

    items: List[Dict[str, Any]] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "category": item.get("category"),
                "checked": bool(item.get("checked", False)),
                "status": item.get("status"),
                "source": item.get("source"),
                "note": item.get("note"),
            }
        )

    return {
        "documentation_only": True,
        "included": bool(items),
        "source_artifact": source_artifact,
        "item_count": len(items),
        "pending_count": sum(1 for item in items if not item.get("checked")),
        "items": items,
        "notice": (
            "Checklist items support operator review only. Checking an item is not "
            "legal approval, LAANC, a waiver, or operational clearance."
        ),
    }


def _approval_checklist_item(
    *,
    check_id: str,
    label: str,
    note: str,
    source: str,
    category: str,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "category": category,
        "checked": False,
        "status": "operator_confirmation_required",
        "source": source,
        "note": note,
    }


def _battery_reserve_checklist_note(
    cfg: Optional[Dict[str, Any]],
    sim: Optional[SimResult],
    constraints: Any,
) -> str:
    vehicle = (cfg or {}).get("vehicle", {}) or {}
    reserve = vehicle.get("battery_reserve_Wh")
    final_battery = _scalar(sim, "final_battery_Wh") if sim is not None else None
    margin = _named_margin(constraints, "battery_reserve") if constraints is not None else None
    details: List[str] = []
    if reserve is not None:
        details.append(f"required reserve {_fmt_value(reserve, 'Wh')}")
    if final_battery is not None:
        details.append(f"planned final battery {_fmt_value(final_battery, 'Wh')}")
    if margin is not None:
        details.append(f"modeled reserve margin {_fmt_value(margin, 'Wh')}")
    suffix = f" ({'; '.join(details)})" if details else ""
    return (
        "Confirm launch battery, reserve policy, payload draw, and abort reserve meet "
        f"operator requirements before release{suffix}."
    )


def _weather_minimums_checklist_note(cfg: Optional[Dict[str, Any]]) -> str:
    weather = _weather_metadata(cfg)
    details: List[str] = []
    if weather.get("source"):
        details.append(f"source {weather['source']}")
    if weather.get("timestamp_utc"):
        details.append(f"timestamp {weather['timestamp_utc']}")
    if weather.get("wind_speed_mps") is not None:
        details.append(f"wind {_fmt_value(weather.get('wind_speed_mps'), 'm/s')}")
    if weather.get("wind_gust_mps") is not None:
        details.append(f"gust {_fmt_value(weather.get('wind_gust_mps'), 'm/s')}")
    suffix = f" Current planning weather: {'; '.join(details)}." if details else ""
    return (
        "Confirm launch-time weather and operator minimums, including wind, gusts, "
        f"visibility, precipitation, and temperature, before flight.{suffix}"
    )


def _operator_approval_checklist(
    *,
    regulatory: Dict[str, Any],
    cfg: Optional[Dict[str, Any]],
    sim: Optional[SimResult],
    constraints: Any,
) -> List[Dict[str, Any]]:
    checklist: List[Dict[str, Any]] = []
    if regulatory.get("laanc_required") is True:
        checklist.append(
            _approval_checklist_item(
                check_id="laanc_confirmation",
                label="Confirm LAANC / controlled-airspace authorization",
                note=(
                    "Scenario sets laanc_required=true; verify authorization evidence, "
                    "flight window, altitude limits, and operating area outside ORBITAL."
                ),
                source="regulatory.laanc_required",
                category="regulatory",
            )
        )
    if regulatory.get("waiver_or_authorization_required") is True:
        checklist.append(
            _approval_checklist_item(
                check_id="waiver_authorization_confirmation",
                label="Confirm waiver / authorization coverage",
                note=(
                    "Scenario indicates a waiver or authorization is required; verify "
                    "document scope, dates, conditions, and mission fit outside ORBITAL."
                ),
                source="regulatory.waiver_or_authorization_required",
                category="regulatory",
            )
        )
    if regulatory.get("visual_observer_required") is True:
        checklist.append(
            _approval_checklist_item(
                check_id="visual_observer_assignment",
                label="Confirm visual observer assignment",
                note=(
                    "Assign visual observer coverage, station locations, communications, "
                    "handoff rules, and responsibilities before dispatch."
                ),
                source="regulatory.visual_observer_required",
                category="crew",
            )
        )

    checklist.extend(
        [
            _approval_checklist_item(
                check_id="crew_briefing",
                label="Confirm crew briefing completed",
                note=(
                    "Brief route, roles, communications, geofences, weather, abort "
                    "criteria, lost-link procedures, and final go/no-go authority."
                ),
                source="operator_review",
                category="crew",
            ),
            _approval_checklist_item(
                check_id="emergency_contingency_plan",
                label="Confirm emergency / contingency plan",
                note=(
                    "Review lost-link response, diversion or landing zones, flyaway "
                    "response, incident contacts, and recovery responsibilities."
                ),
                source="operator_review",
                category="safety",
            ),
            _approval_checklist_item(
                check_id="notam_local_restriction_review",
                label="Confirm NOTAM / local restriction review",
                note=(
                    "Review current NOTAMs, TFRs, local restrictions, site permissions, "
                    "and customer constraints close to flight time."
                ),
                source="operator_review",
                category="regulatory",
            ),
            _approval_checklist_item(
                check_id="weather_minimums_confirmation",
                label="Confirm weather minimums",
                note=_weather_minimums_checklist_note(cfg),
                source="weather",
                category="weather",
            ),
            _approval_checklist_item(
                check_id="battery_reserve_confirmation",
                label="Confirm battery reserve",
                note=_battery_reserve_checklist_note(cfg, sim, constraints),
                source="vehicle.battery_reserve_Wh",
                category="energy",
            ),
        ]
    )
    return checklist


def build_regulatory_readiness_report(
    plan: Plan,
    sim: Optional[SimResult] = None,
    constraints: Any = None,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a regulatory readiness report for operator review, not approval."""
    regulatory = _regulatory_metadata(cfg)
    mission_metadata = _mission_metadata(cfg)
    fleet_metadata = _fleet_metadata(cfg)
    regulatory_evidence = _regulatory_evidence_fields(regulatory)

    regulatory_summary = {
        "laanc_required": _regulatory_summary_item(
            key="laanc_required",
            label="LAANC required",
            value=regulatory.get("laanc_required"),
            yes_summary="Scenario indicates LAANC or controlled-airspace authorization is required before flight.",
            no_summary="Scenario indicates LAANC is not required, subject to operator verification against current airspace data.",
            unknown_summary="Scenario does not state whether LAANC is required.",
        ),
        "waiver_or_authorization_required": _regulatory_summary_item(
            key="waiver_or_authorization_required",
            label="Waiver / authorization required",
            value=regulatory.get("waiver_or_authorization_required"),
            yes_summary="Scenario indicates a waiver or authorization is required before flight.",
            no_summary="Scenario indicates no waiver or authorization requirement was identified, subject to operator verification.",
            unknown_summary="Scenario does not state whether a waiver or authorization is required.",
        ),
        "airspace_class": {
            "id": "airspace_class",
            "label": "Airspace class",
            "value": regulatory.get("airspace_class"),
            "configured": regulatory.get("airspace_class"),
            "status": "provided" if regulatory.get("airspace_class") else "unknown",
            "summary": (
                f"Scenario airspace class is {regulatory.get('airspace_class')}."
                if regulatory.get("airspace_class")
                else "Scenario does not provide an airspace class."
            ),
        },
        "visual_observer_required": _regulatory_summary_item(
            key="visual_observer_required",
            label="Visual observer required",
            value=regulatory.get("visual_observer_required"),
            yes_summary="Scenario indicates visual observer support is required.",
            no_summary="Scenario indicates visual observer support is not required, subject to operator verification.",
            unknown_summary="Scenario does not state whether visual observer support is required.",
        ),
        "ground_risk_population_note": {
            "id": "ground_risk_population_note",
            "label": "Ground-risk / population note",
            "value": regulatory.get("ground_risk_population_note"),
            "configured": regulatory.get("ground_risk_population_note"),
            "status": "provided" if regulatory.get("ground_risk_population_note") else "missing",
            "summary": regulatory.get("ground_risk_population_note")
            or "Ground-risk / population note was not provided.",
        },
    }

    unresolved_items = _regulatory_unresolved_items(regulatory)
    readiness_state = _regulatory_readiness_state(regulatory)
    return {
        "kind": "regulatory_readiness_report",
        "mission_id": plan.metadata.get("mission_id", "aircraft_mission"),
        "status": readiness_state,
        "readiness_state": readiness_state,
        "documentation_only": True,
        "decision_support_only": True,
        "not_legal_approval": True,
        "disclaimer": REGULATORY_READINESS_DISCLAIMER,
        "not_legal_approval_disclaimer": REGULATORY_READINESS_DISCLAIMER,
        "mission_metadata": mission_metadata,
        "fleet_metadata": fleet_metadata,
        "regulatory_summary": regulatory_summary,
        "regulatory_evidence": regulatory_evidence,
        "operating_assumptions": _regulatory_operating_assumptions(regulatory),
        "unresolved_regulatory_items": unresolved_items,
        "operator_approval_checklist": _operator_approval_checklist(
            regulatory=regulatory,
            cfg=cfg,
            sim=sim,
            constraints=constraints,
        ),
        "documentation_only_notice": regulatory.get("documentation_only_notice"),
        "operator_review_required": True,
        "mission_context": {
            "hard_constraints_pass": (
                None if constraints is None else bool(getattr(constraints, "hard_pass", False))
            ),
            "inspection_points": max(0, len(plan.waypoints or []) - 1),
            "estimated_time_s": _scalar(sim, "t_end_s") if sim is not None else None,
            "energy_used_Wh": _scalar(sim, "energy_used_Wh") if sim is not None else None,
            "waypoints_completed": _scalar(sim, "waypoints_completed") if sim is not None else None,
            "waypoints_total": _scalar(sim, "waypoints_total") if sim is not None else None,
        },
        "robustness": robustness or {},
    }


def format_regulatory_readiness_report(report: Dict[str, Any]) -> str:
    """Render the regulatory readiness report as Markdown."""
    summary = report.get("regulatory_summary") or {}
    evidence = report.get("regulatory_evidence") or {}
    mission_metadata = report.get("mission_metadata") or {}
    fleet_metadata = report.get("fleet_metadata") or {}

    def fmt_list(values: Any) -> str:
        items = [str(item) for item in values or [] if str(item).strip()]
        return ", ".join(items) if items else "not provided"

    def fmt_time_window(window: Any) -> str:
        if not isinstance(window, dict) or not window:
            return "not provided"
        start = window.get("start_utc") or "not provided"
        end = window.get("end_utc") or "not provided"
        return f"{start} to {end}"

    def display_status(key: str, item: Dict[str, Any]) -> str:
        if key in {
            "laanc_required",
            "waiver_or_authorization_required",
            "visual_observer_required",
        }:
            return _yes_no_unknown(item.get("value"))
        if key == "airspace_class":
            return str(item.get("value") or "unknown")
        return str(item.get("status", "unknown"))

    lines = [
        "# Regulatory Readiness Report",
        "",
        f"Mission: {report.get('mission_id', 'aircraft_mission')}",
        f"Readiness state: {str(report.get('readiness_state', 'unknown')).upper()}",
        "",
        "## Not Legal Approval",
        "",
        str(report.get("not_legal_approval_disclaimer") or REGULATORY_READINESS_DISCLAIMER),
        "",
        "## Mission / Fleet Context",
        "",
        f"- Operator: {mission_metadata.get('operator') or 'not provided'}",
        f"- Aircraft ID: {mission_metadata.get('aircraft_id') or 'not provided'}",
        f"- Pilot: {mission_metadata.get('pilot') or 'not provided'}",
        f"- Organization: {mission_metadata.get('organization') or 'not provided'}",
        f"- Asset owner: {mission_metadata.get('asset_owner') or 'not provided'}",
        f"- Drone model: {fleet_metadata.get('drone_model') or 'not provided'}",
        f"- Inspection type: {fleet_metadata.get('inspection_type') or 'not provided'}",
        "",
        "## Regulatory Summary",
        "",
    ]
    for key in (
        "laanc_required",
        "waiver_or_authorization_required",
        "airspace_class",
        "visual_observer_required",
        "ground_risk_population_note",
    ):
        item = summary.get(key) or {}
        lines.append(
            "- {label}: {status} - {detail}".format(
                label=item.get("label", key),
                status=display_status(key, item),
                detail=item.get("summary", "not provided"),
            )
        )

    lines.extend(
        [
            "",
            "## Regulatory Evidence Fields",
            "",
            str(
                evidence.get("notice")
                or "Optional documentation-only evidence fields; ORBITAL does not verify them."
            ),
            "",
            "- Authorization ID / reference number: "
            f"{evidence.get('authorization_id') or 'not provided'}",
            "- Authorization authority: "
            f"{evidence.get('authorization_authority') or 'not provided'}",
            "- Approving authority / source: "
            f"{evidence.get('approving_authority_source') or 'not provided'}",
            "- Authorization date checked: "
            f"{evidence.get('authorization_date_checked_utc') or 'not provided'}",
            "- Authorization expiration date: "
            f"{evidence.get('authorization_expiration_date') or 'not provided'}",
            "- Operator confirmation status: "
            f"{evidence.get('operator_confirmation_status') or 'not provided'}",
            "- Operating altitude limit: "
            f"{_fmt_value(evidence.get('operating_altitude_limit_m'), 'm')}",
            "- Operating time window: " f"{fmt_time_window(evidence.get('operating_time_window'))}",
            f"- Required crew roles: {fmt_list(evidence.get('required_crew_roles'))}",
            "- Special conditions / limitations: "
            f"{fmt_list(evidence.get('special_conditions_limitations'))}",
            "- Emergency / contingency plan: "
            f"{evidence.get('emergency_contingency_plan') or 'not provided'}",
        ]
    )

    lines.extend(
        [
            "",
            "## Operating Assumptions",
            "",
        ]
    )
    for assumption in report.get("operating_assumptions", []) or []:
        lines.append(f"- {assumption}")

    lines.extend(
        [
            "",
            "## Operator Approval Checklist",
            "",
            "These items are operator confirmations only; checking them does not make "
            "ORBITAL a legal approval or clearance system.",
            "",
        ]
    )
    checklist = report.get("operator_approval_checklist") or []
    if checklist:
        for item in checklist:
            lines.append(
                "- [ ] {label}: {note}".format(
                    label=item.get("label", "Operator confirmation"),
                    note=item.get("note", "Operator confirmation required."),
                )
            )
    else:
        lines.append("- [ ] Complete operator review before flight.")

    lines.extend(
        [
            "",
            "## Unresolved Regulatory Items",
            "",
        ]
    )
    unresolved = report.get("unresolved_regulatory_items", []) or []
    if unresolved:
        for item in unresolved:
            lines.append(
                "- {label}: {status} - {note}".format(
                    label=item.get("label", "Regulatory item"),
                    status=str(item.get("status", "unknown")).upper(),
                    note=item.get("note", "Operator review required."),
                )
            )
    else:
        lines.append("- No scenario-specific unresolved items were identified by ORBITAL.")

    lines.extend(
        [
            "",
            "## Documentation-Only Notice",
            "",
            str(report.get("documentation_only_notice") or "Not provided."),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_regulatory_readiness_report(
    plan: Plan,
    sim: Optional[SimResult],
    constraints: Any,
    out_dir: Path,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write regulatory readiness JSON and Markdown artifacts."""
    report = build_regulatory_readiness_report(
        plan,
        sim,
        constraints,
        cfg=cfg,
        robustness=robustness,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_strict_json(out_dir / "regulatory_readiness_report.json", report)
    (out_dir / "regulatory_readiness_report.md").write_text(
        format_regulatory_readiness_report(report),
        encoding="utf-8",
    )
    return report


def _what_if_planner_config(cfg: Dict[str, Any], seed: int) -> PlannerConfig:
    planner_cfg = cfg.get("planner", {}) or {}
    mutation_cfg = planner_cfg.get("mutation", {}) or {}
    iterations = min(80, int(planner_cfg.get("iterations", 80)))
    return PlannerConfig(
        iterations=iterations,
        restarts=1,
        seed=seed,
        keep_history=False,
        scoring=ScoreConfig(
            penalty_weight=float(planner_cfg.get("penalty_weight", 1000.0)),
            margin_reward_weight=float(planner_cfg.get("margin_reward_weight", 0.0)),
        ),
        hard_infeasible_penalty=float(planner_cfg.get("hard_infeasible_penalty", 1e6)),
        mutation=MutationConfig(
            cont_sigma=float(mutation_cfg.get("cont_sigma", 0.10)),
            cont_sigma_is_frac=bool(mutation_cfg.get("cont_sigma_is_frac", True)),
            int_step=int(mutation_cfg.get("int_step", 1)),
            p_flip=float(mutation_cfg.get("p_flip", 0.05)),
            p_perm_swap=float(mutation_cfg.get("p_perm_swap", 0.50)),
            perm_swaps=int(mutation_cfg.get("perm_swaps", 2)),
        ),
    )


def _what_if_run_cfg(cfg: Dict[str, Any], seed: int) -> Dict[str, Any]:
    run_cfg = deepcopy(cfg)
    run_cfg.setdefault("robustness", {})
    run_cfg["robustness"]["cases"] = 0
    run_cfg.setdefault("planner", {})
    run_cfg["planner"]["seed"] = seed
    run_cfg["planner"]["iterations"] = min(80, int(run_cfg["planner"].get("iterations", 80)))
    run_cfg["planner"]["restarts"] = 1
    run_cfg.setdefault("output", {})
    run_cfg["output"]["save_history"] = False
    return run_cfg


def _solve_what_if_cfg(cfg: Dict[str, Any], seed: int) -> Any:
    from mission_framework.aircraft.mission import build_problem_from_config

    run_cfg = _what_if_run_cfg(cfg, seed)
    problem = build_problem_from_config(run_cfg)
    return Planner(_what_if_planner_config(run_cfg, seed)).solve(problem)


def _audit_check(audit: Dict[str, Any], check_id: str) -> Dict[str, Any]:
    for check in audit.get("checks", []) or []:
        if check.get("id") == check_id:
            return check
    return {}


def _check_margin_value(audit: Dict[str, Any], check_id: str) -> Optional[float]:
    check = _audit_check(audit, check_id)
    margin = check.get("margin") or {}
    value = margin.get("value")
    return None if value is None else float(value)


def _risk_rank(risk: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(risk).lower(), 3)


WHAT_IF_IMPROVEMENT_METRICS = [
    ("battery_reserve_margin_Wh", "Battery reserve margin", "Wh"),
    ("wind_weather_margin_mps", "Wind / weather margin", "m/s"),
    ("geofence_clearance_margin_m", "Geofence clearance margin", "m"),
    ("route_completion_margin", "Route completion margin", "completion"),
    ("turn_bank_margin_radps", "Turn / bank margin", "rad/s"),
]


def _metric_improvement(
    *,
    metric_id: str,
    label: str,
    unit: str,
    baseline: Dict[str, Any],
    variant: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    before = baseline.get(metric_id)
    after = variant.get(metric_id)
    if before is None or after is None:
        return None
    delta = float(after) - float(before)
    if delta <= 1e-9:
        return None
    return {
        "metric": metric_id,
        "label": label,
        "unit": unit,
        "before": float(before),
        "after": float(after),
        "delta": delta,
    }


def _what_if_before_after_improvements(
    baseline: Dict[str, Any], variants: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    improvements: List[Dict[str, Any]] = []
    baseline_risk_rank = _risk_rank(str(baseline.get("mission_risk", "unknown")))
    baseline_feasible = bool(baseline.get("feasible"))

    for variant in variants:
        variant_improvements: List[Dict[str, Any]] = []
        if not baseline_feasible and bool(variant.get("feasible")):
            variant_improvements.append(
                {
                    "metric": "feasibility",
                    "label": "Feasibility",
                    "unit": "status",
                    "before": "not feasible",
                    "after": "feasible",
                    "delta": "improved",
                }
            )

        variant_risk_rank = _risk_rank(str(variant.get("mission_risk", "unknown")))
        if variant_risk_rank < baseline_risk_rank:
            variant_improvements.append(
                {
                    "metric": "mission_risk",
                    "label": "Mission risk",
                    "unit": "risk",
                    "before": str(baseline.get("mission_risk", "unknown")),
                    "after": str(variant.get("mission_risk", "unknown")),
                    "delta": "lower",
                }
            )

        for metric_id, label, unit in WHAT_IF_IMPROVEMENT_METRICS:
            improvement = _metric_improvement(
                metric_id=metric_id,
                label=label,
                unit=unit,
                baseline=baseline,
                variant=variant,
            )
            if improvement is not None:
                variant_improvements.append(improvement)

        if variant_improvements:
            improvements.append(
                {
                    "variant_id": variant.get("id"),
                    "label": variant.get("label"),
                    "description": variant.get("description"),
                    "improvements": variant_improvements,
                    "summary": _what_if_improvement_summary(variant_improvements),
                }
            )

    return improvements


def _what_if_improvement_summary(improvements: List[Dict[str, Any]]) -> str:
    labels = [str(item.get("label")) for item in improvements[:3] if item.get("label")]
    if not labels:
        return "Improves feasibility evidence versus the baseline."
    if len(labels) == 1:
        return f"Improves {labels[0].lower()} versus the baseline."
    return (
        "Improves "
        + ", ".join(label.lower() for label in labels[:-1])
        + (f", and {labels[-1].lower()} versus the baseline.")
    )


def _fmt_improvement_value(value: Any, unit: str = "") -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _fmt_value(float(value), unit)
    suffix = f" {unit}" if unit and str(unit).lower() not in {"status", "risk"} else ""
    return f"{value}{suffix}"


def _signed_delta_text(after: Any, before: Any, unit: str) -> Optional[str]:
    if after is None or before is None:
        return None
    try:
        delta = float(after) - float(before)
    except (TypeError, ValueError):
        return None
    if abs(delta) < 1e-9:
        return f"no change {unit}".strip()
    sign = "+" if delta > 0 else ""
    return f"{sign}{_fmt_value(delta, unit)}"


def _what_if_change_sentence(variant: Dict[str, Any], baseline: Dict[str, Any]) -> str:
    parts = []
    for label, key, unit in (
        ("time", "estimated_time_s", "s"),
        ("energy", "energy_used_Wh", "Wh"),
        ("battery reserve", "battery_reserve_margin_Wh", "Wh"),
        ("wind margin", "wind_weather_margin_mps", "m/s"),
    ):
        delta = _signed_delta_text(variant.get(key), baseline.get(key), unit)
        if delta and not delta.startswith("no change"):
            parts.append(f"{label} {delta}")
    if not parts:
        return "No material modeled change versus baseline."
    return "Changed " + ", ".join(parts[:3]) + "."


def _dedupe_risk_drivers(drivers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for driver in drivers:
        driver_id = str(driver.get("id", driver.get("label", "")))
        current = by_id.get(driver_id)
        if current is None or float(driver.get("risk_points", 0.0)) > float(
            current.get("risk_points", 0.0)
        ):
            by_id[driver_id] = driver
    return sorted(
        by_id.values(),
        key=lambda item: float(item.get("risk_points", 0.0)),
        reverse=True,
    )


def _variant_summary(
    *,
    variant_id: str,
    label: str,
    description: str,
    result: Any,
    cfg: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Dict[str, Any]:
    audit = build_inspection_constraint_audit(
        result.plan,
        result.sim_result,
        result.constraints,
        cfg=cfg,
        robustness=result.robustness,
    )
    time_s = _scalar(result.sim_result, "t_end_s")
    energy_wh = _scalar(result.sim_result, "energy_used_Wh")
    final_battery_wh = _scalar(result.sim_result, "final_battery_Wh")
    baseline_time = baseline.get("estimated_time_s")
    baseline_energy = baseline.get("energy_used_Wh")
    return {
        "id": variant_id,
        "label": label,
        "description": description,
        "feasible": bool(result.constraints.hard_pass),
        "mission_risk": audit["mission_risk"],
        "score": float(result.score),
        "estimated_time_s": time_s,
        "energy_used_Wh": energy_wh,
        "final_battery_Wh": final_battery_wh,
        "battery_reserve_margin_Wh": _check_margin_value(audit, "battery_reserve"),
        "wind_weather_margin_mps": _check_margin_value(audit, "wind_weather"),
        "geofence_clearance_margin_m": _check_margin_value(audit, "geofence_clearance"),
        "route_completion_margin": _check_margin_value(audit, "route_completion"),
        "turn_bank_margin_radps": _check_margin_value(audit, "turn_bank_feasibility"),
        "top_limiting_constraint": audit.get("top_limiting_constraint"),
        "top_three_risk_drivers": audit.get("top_three_risk_drivers", []),
        "delta_vs_baseline": {
            "estimated_time_s": (
                None if time_s is None or baseline_time is None else float(time_s - baseline_time)
            ),
            "energy_used_Wh": (
                None
                if energy_wh is None or baseline_energy is None
                else float(energy_wh - baseline_energy)
            ),
        },
    }


def _base_summary_from_audit(
    *,
    result_score: float,
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    audit: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": "baseline",
        "label": "Current BVLOS plan",
        "feasible": bool(getattr(constraints, "hard_pass", False)),
        "mission_risk": audit["mission_risk"],
        "score": float(result_score),
        "inspection_points": max(0, len(plan.waypoints or []) - 1),
        "estimated_time_s": _scalar(sim, "t_end_s"),
        "energy_used_Wh": _scalar(sim, "energy_used_Wh"),
        "final_battery_Wh": _scalar(sim, "final_battery_Wh"),
        "battery_reserve_margin_Wh": _check_margin_value(audit, "battery_reserve"),
        "wind_weather_margin_mps": _check_margin_value(audit, "wind_weather"),
        "geofence_clearance_margin_m": _check_margin_value(audit, "geofence_clearance"),
        "route_completion_margin": _check_margin_value(audit, "route_completion"),
        "turn_bank_margin_radps": _check_margin_value(audit, "turn_bank_feasibility"),
    }


def _fewer_waypoints_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    waypoints = list((out.get("mission", {}) or {}).get("waypoints", []) or [])
    keep = max(1, len(waypoints) - 2) if len(waypoints) >= 4 else max(1, len(waypoints) - 1)
    out["mission"]["waypoints"] = waypoints[:keep]
    return out


def _lower_speed_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    vehicle = out.get("vehicle", {}) or {}
    min_speed = float(vehicle.get("min_speed_mps", 12.0))
    cruise = float(vehicle.get("cruise_speed_mps", min_speed))
    lower_speed = max(min_speed, cruise * 0.8)
    vehicle["min_speed_mps"] = lower_speed
    vehicle["max_speed_mps"] = lower_speed
    vehicle["cruise_speed_mps"] = lower_speed
    out["vehicle"] = vehicle
    return out


def _alternate_launch_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    initial = out.get("initial_state", {}) or {}
    waypoints = list((out.get("mission", {}) or {}).get("waypoints", []) or [])
    if waypoints:
        first = waypoints[0]
        initial["x_m"] = float(initial.get("x_m", 0.0)) * 0.5 + float(first["x_m"]) * 0.5
        initial["y_m"] = float(initial.get("y_m", 0.0)) * 0.5 + float(first["y_m"]) * 0.5
    out["initial_state"] = initial
    return out


def _stronger_wind_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    wind = out.get("wind", {}) or {}
    for key in (
        "w_east_mps",
        "w_north_mps",
        "mean_east_mps",
        "mean_north_mps",
        "amp_east_mps",
        "amp_north_mps",
        "gust_amplitude_mps",
    ):
        if key in wind:
            wind[key] = float(wind[key]) * 1.5
    out["wind"] = wind
    return out


def _larger_reserve_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cfg)
    vehicle = out.get("vehicle", {}) or {}
    capacity = float(vehicle.get("battery_capacity_Wh", 0.0))
    current_reserve = float(vehicle.get("battery_reserve_Wh", 0.0))
    larger_reserve = max(current_reserve + 100.0, current_reserve * 1.15)
    if capacity > 0.0:
        larger_reserve = min(capacity * 0.95, larger_reserve)
    vehicle["battery_reserve_Wh"] = larger_reserve
    out["vehicle"] = vehicle
    out.setdefault("constraints", {})
    out["constraints"]["enforce_battery_reserve"] = True
    return out


def _relaunch_sortie_cfgs(cfg: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    waypoints = list((cfg.get("mission", {}) or {}).get("waypoints", []) or [])
    if len(waypoints) < 2:
        return None

    split = int(np.ceil(len(waypoints) / 2.0))
    first_leg = deepcopy(cfg)
    second_leg = deepcopy(cfg)
    first_leg["mission"]["waypoints"] = waypoints[:split]
    second_leg["mission"]["waypoints"] = waypoints[split:]
    if not second_leg["mission"]["waypoints"]:
        return None

    swap_point = waypoints[split - 1]
    second_initial = second_leg.get("initial_state", {}) or {}
    second_initial["x_m"] = float(swap_point["x_m"])
    second_initial["y_m"] = float(swap_point["y_m"])
    second_initial["z_m"] = float(swap_point.get("z_m", second_initial.get("z_m", 0.0)))
    vehicle = second_leg.get("vehicle", {}) or {}
    capacity = float(vehicle.get("battery_capacity_Wh", second_initial.get("battery_Wh", 0.0)))
    original_initial = float((cfg.get("initial_state", {}) or {}).get("battery_Wh", capacity))
    second_initial["battery_Wh"] = min(capacity, original_initial)
    second_leg["initial_state"] = second_initial
    return [first_leg, second_leg]


def _relaunch_summary(
    *,
    cfg: Dict[str, Any],
    baseline: Dict[str, Any],
    seed: int,
) -> Optional[Dict[str, Any]]:
    sortie_cfgs = _relaunch_sortie_cfgs(cfg)
    if sortie_cfgs is None:
        return None

    sortie_summaries = []
    for index, sortie_cfg in enumerate(sortie_cfgs):
        result = _solve_what_if_cfg(sortie_cfg, seed + index)
        sortie_summaries.append(
            _variant_summary(
                variant_id=f"relaunch_battery_swap_sortie_{index + 1}",
                label=f"Relaunch / battery swap sortie {index + 1}",
                description="One sortie in a split-route battery swap option.",
                result=result,
                cfg=sortie_cfg,
                baseline=baseline,
            )
        )

    total_time = sum(float(s.get("estimated_time_s") or 0.0) for s in sortie_summaries)
    total_energy = sum(float(s.get("energy_used_Wh") or 0.0) for s in sortie_summaries)
    feasible = all(bool(s["feasible"]) for s in sortie_summaries)
    worst_risk = max((str(s["mission_risk"]) for s in sortie_summaries), key=_risk_rank)
    drivers = _dedupe_risk_drivers(
        driver
        for summary in sortie_summaries
        for driver in summary.get("top_three_risk_drivers", [])[:3]
    )[:3]
    baseline_time = baseline.get("estimated_time_s")
    baseline_energy = baseline.get("energy_used_Wh")
    return {
        "id": "relaunch_battery_swap",
        "label": "Relaunch / battery swap",
        "description": "Split the route into two sorties with a fresh battery for the second leg.",
        "feasible": feasible,
        "mission_risk": worst_risk,
        "score": sum(float(s.get("score") or 0.0) for s in sortie_summaries),
        "estimated_time_s": total_time,
        "energy_used_Wh": total_energy,
        "final_battery_Wh": min(float(s.get("final_battery_Wh") or 0.0) for s in sortie_summaries),
        "battery_reserve_margin_Wh": min(
            float(s.get("battery_reserve_margin_Wh") or 0.0) for s in sortie_summaries
        ),
        "wind_weather_margin_mps": min(
            float(s.get("wind_weather_margin_mps") or 0.0) for s in sortie_summaries
        ),
        "geofence_clearance_margin_m": min(
            float(s.get("geofence_clearance_margin_m") or 0.0) for s in sortie_summaries
        ),
        "route_completion_margin": min(
            float(s.get("route_completion_margin") or 0.0) for s in sortie_summaries
        ),
        "turn_bank_margin_radps": min(
            float(s.get("turn_bank_margin_radps") or 0.0) for s in sortie_summaries
        ),
        "top_limiting_constraint": drivers[0] if drivers else None,
        "top_three_risk_drivers": drivers,
        "sorties": sortie_summaries,
        "delta_vs_baseline": {
            "estimated_time_s": (
                None if baseline_time is None else float(total_time - float(baseline_time))
            ),
            "energy_used_Wh": (
                None if baseline_energy is None else float(total_energy - float(baseline_energy))
            ),
        },
    }


def build_what_if_plan(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    *,
    cfg: Dict[str, Any],
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare practical BVLOS inspection what-if planning options."""
    base_audit = build_inspection_constraint_audit(
        plan,
        sim,
        constraints,
        cfg=cfg,
        robustness=robustness,
    )
    baseline = _base_summary_from_audit(
        result_score=float(getattr(score_report, "total_score", 0.0)),
        plan=plan,
        sim=sim,
        constraints=constraints,
        audit=base_audit,
    )
    seed = int((cfg.get("planner", {}) or {}).get("seed", 0)) + 1000
    variant_specs = [
        (
            "fewer_waypoints",
            "Fewer waypoints",
            "Drop the final inspection points to compare a shorter sortie.",
            _fewer_waypoints_cfg,
        ),
        (
            "lower_speed",
            "Lower speed",
            "Force a lower cruise speed to compare endurance and turn margin.",
            _lower_speed_cfg,
        ),
        (
            "alternate_launch_point",
            "Alternate launch point",
            "Move launch closer to the first tower / inspection corridor.",
            _alternate_launch_cfg,
        ),
        (
            "stronger_wind",
            "Stronger wind case",
            "Increase modeled wind components by 50 percent.",
            _stronger_wind_cfg,
        ),
        (
            "larger_battery_reserve",
            "Larger battery reserve requirement",
            "Increase the required final battery reserve.",
            _larger_reserve_cfg,
        ),
    ]

    variants = []
    for index, (variant_id, label, description, factory) in enumerate(variant_specs):
        variant_cfg = factory(cfg)
        result = _solve_what_if_cfg(variant_cfg, seed + index)
        variants.append(
            _variant_summary(
                variant_id=variant_id,
                label=label,
                description=description,
                result=result,
                cfg=variant_cfg,
                baseline=baseline,
            )
        )

    relaunch = _relaunch_summary(cfg=cfg, baseline=baseline, seed=seed + len(variant_specs))
    if relaunch is not None:
        variants.append(relaunch)

    before_after_improvements = _what_if_before_after_improvements(baseline, variants)
    return {
        "kind": "drone_inspection_what_if_plan",
        "mission_id": plan.metadata.get("mission_id", "aircraft_mission"),
        "baseline": baseline,
        "variants": variants,
        "before_after_improvements": before_after_improvements,
    }


def format_what_if_plan(payload: Dict[str, Any]) -> str:
    """Render what-if planning comparisons as Markdown."""
    lines = [
        "# BVLOS What-If Planning",
        "",
        f"Mission: {payload.get('mission_id', 'aircraft_mission')}",
        "",
        "## Baseline",
        "",
        "| Risk | Feasible | Time (s) | Energy (Wh) | Battery margin (Wh) | Wind margin (m/s) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    base = payload.get("baseline", {}) or {}
    lines.append(
        "| {risk} | {feasible} | {time} | {energy} | {battery} | {wind} |".format(
            risk=str(base.get("mission_risk", "unknown")).upper(),
            feasible="yes" if base.get("feasible") else "no",
            time=_fmt_value(base.get("estimated_time_s")),
            energy=_fmt_value(base.get("energy_used_Wh")),
            battery=_fmt_value(base.get("battery_reserve_margin_Wh")),
            wind=_fmt_value(base.get("wind_weather_margin_mps")),
        )
    )

    lines.extend(
        [
            "",
            "## Scenario Comparisons",
            "",
            "| Scenario | What changed | Risk | Feasible | Time (s) | Delta Time | Energy (Wh) | "
            "Battery Margin | Top Limiter |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for variant in payload.get("variants", []) or []:
        top = variant.get("top_limiting_constraint") or {}
        delta = variant.get("delta_vs_baseline") or {}
        lines.append(
            "| {label} | {change} | {risk} | {feasible} | {time} | {delta_time} | {energy} | "
            "{battery} | {limiter} |".format(
                label=_markdown_cell(variant.get("label", "Scenario")),
                change=_markdown_cell(_what_if_change_sentence(variant, base)),
                risk=str(variant.get("mission_risk", "unknown")).upper(),
                feasible="yes" if variant.get("feasible") else "no",
                time=_fmt_value(variant.get("estimated_time_s")),
                delta_time=_fmt_value(delta.get("estimated_time_s")),
                energy=_fmt_value(variant.get("energy_used_Wh")),
                battery=_fmt_value(variant.get("battery_reserve_margin_Wh")),
                limiter=top.get("label", "n/a"),
            )
        )

    improvements = payload.get("before_after_improvements") or []
    if improvements:
        lines.extend(
            [
                "",
                "## Before / After Improvements",
                "",
                "These scenarios improve at least one feasibility or audit margin versus "
                "the baseline plan.",
                "",
                "| Scenario | Improved metric | Baseline | After | Delta |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for scenario in improvements:
            for improvement in scenario.get("improvements", []) or []:
                unit = str(improvement.get("unit") or "")
                lines.append(
                    "| {scenario} | {metric} | {before} | {after} | {delta} |".format(
                        scenario=_markdown_cell(scenario.get("label") or "Scenario"),
                        metric=_markdown_cell(improvement.get("label") or "Metric"),
                        before=_markdown_cell(
                            _fmt_improvement_value(improvement.get("before"), unit)
                        ),
                        after=_markdown_cell(
                            _fmt_improvement_value(improvement.get("after"), unit)
                        ),
                        delta=_markdown_cell(
                            _fmt_improvement_value(improvement.get("delta"), unit)
                        ),
                    )
                )
    else:
        lines.extend(
            [
                "",
                "## Before / After Improvements",
                "",
                "No what-if scenario improved a feasibility or audit margin versus the "
                "baseline plan.",
            ]
        )

    lines.extend(["", "## Notes", ""])
    for variant in payload.get("variants", []) or []:
        lines.append(f"- {variant.get('label', 'Scenario')}: {variant.get('description', '')}")
    return "\n".join(lines).rstrip() + "\n"


def export_what_if_plan(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    out_dir: Path,
    *,
    cfg: Dict[str, Any],
    robustness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write BVLOS what-if planning JSON and Markdown artifacts."""
    payload = build_what_if_plan(
        plan,
        sim,
        constraints,
        score_report,
        cfg=cfg,
        robustness=robustness,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_strict_json(out_dir / "what_if_plan.json", payload)
    (out_dir / "what_if_plan.md").write_text(format_what_if_plan(payload), encoding="utf-8")
    return payload


def _evidence_bundle_review_metadata(
    cfg: Optional[Dict[str, Any]],
    *,
    artifacts_complete: bool,
    missing_regulatory_evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    bundle_cfg = (cfg or {}).get("evidence_bundle", {}) or {}
    configured_status = bundle_cfg.get("operator_review_status") or bundle_cfg.get("review_status")
    requested_status = None
    if configured_status is None:
        status = (
            "ready_for_review"
            if artifacts_complete and not missing_regulatory_evidence
            else "draft"
        )
    else:
        requested_status = (
            str(configured_status).strip().lower().replace(" ", "_").replace("-", "_")
        )
        status = requested_status
    if status not in {"draft", "ready_for_review", "reviewed"}:
        status = "draft"
    if not artifacts_complete or missing_regulatory_evidence:
        status = "draft"
    return {
        "status": status,
        "requested_status": requested_status,
        "allowed_statuses": ["draft", "ready_for_review", "reviewed"],
        "reviewer_name": bundle_cfg.get("reviewer_name"),
        "review_timestamp_utc": bundle_cfg.get("review_timestamp_utc"),
        "review_notes": bundle_cfg.get("review_notes"),
        "operator_decision": bundle_cfg.get("operator_decision"),
        "documentation_only": True,
        "notice": (
            "Operator review fields are documentation only. They do not approve a flight, "
            "issue an authorization, provide legal advice, or replace pilot-in-command "
            "release authority."
        ),
    }


def _bundle_completeness(manifest_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(manifest_entries)
    present = sum(1 for entry in manifest_entries if entry.get("present"))
    missing = total - present
    score = 100.0 if total == 0 else round((present / total) * 100.0, 1)
    return {
        "score": score,
        "unit": "percent",
        "present_artifacts": present,
        "total_artifacts": total,
        "missing_artifacts": missing,
        "complete": missing == 0,
        "scoring_note": (
            "Score is based on expected bundle artifacts present at export time. "
            "Optional documentation fields are reported separately and do not block planning."
        ),
    }


def _bundle_missing_evidence(
    manifest_entries: List[Dict[str, Any]],
    regulatory_evidence_status: Dict[str, Any],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for entry in manifest_entries:
        if entry.get("present"):
            continue
        missing.append(
            {
                "kind": "artifact",
                "id": entry.get("id"),
                "label": entry.get("label"),
                "bundle_path": entry.get("bundle_path"),
                "documentation_only": False,
                "operator_attention": True,
                "note": "Expected evidence artifact is missing from the bundle.",
            }
        )
    for item in regulatory_evidence_status.get("missing", []) or []:
        missing.append(
            {
                "kind": "regulatory_documentation",
                "id": item.get("id"),
                "label": item.get("label"),
                "path": item.get("path"),
                "documentation_only": True,
                "operator_attention": bool(item.get("operator_attention")),
                "note": item.get("note"),
            }
        )
    return missing


def _generated_bundle_artifacts() -> List[Dict[str, Any]]:
    return [
        {
            "id": "operator_review_ui",
            "label": "Lightweight operator review web UI",
            "bundle_path": "operator_review_ui.html",
            "present": True,
            "generated": True,
            "artifact_format": "html",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "operator_dashboard",
            "label": "Operator evidence dashboard",
            "bundle_path": "operator_dashboard.md",
            "present": True,
            "generated": True,
            "artifact_format": "markdown",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "bundle_summary",
            "label": "Evidence bundle summary",
            "bundle_path": "evidence_bundle_summary.md",
            "present": True,
            "generated": True,
            "artifact_format": "markdown",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "artifact_index",
            "label": "Evidence bundle artifact index",
            "bundle_path": "artifact_index.md",
            "present": True,
            "generated": True,
            "artifact_format": "markdown",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "manifest_json",
            "label": "Evidence bundle manifest",
            "bundle_path": "manifest.json",
            "present": True,
            "generated": True,
            "artifact_format": "json",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "readme",
            "label": "Evidence bundle README",
            "bundle_path": "README.md",
            "present": True,
            "generated": True,
            "artifact_format": "markdown",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
        {
            "id": "checksum_manifest",
            "label": "Evidence bundle checksum manifest",
            "bundle_path": "checksum_manifest.json",
            "present": True,
            "generated": True,
            "artifact_format": "json",
            "opens_outside_ui": True,
            "ui_link_behavior": "link_when_present_else_unavailable_label",
        },
    ]


def _artifact_format(bundle_path: Any) -> str:
    suffix = Path(str(bundle_path or "")).suffix.strip(".").lower()
    formats = {
        "md": "markdown",
        "json": "json",
        "csv": "csv",
        "kml": "kml",
        "png": "png",
        "html": "html",
        "yaml": "yaml",
        "yml": "yaml",
    }
    return formats.get(suffix, suffix or "file")


def _artifact_link(bundle_path: Any, label: Any = None) -> str:
    path = str(bundle_path or "").strip()
    text = str(label or path or "artifact").strip()
    if not path:
        return text
    href = path.replace("\\", "/").replace(" ", "%20")
    return f"[{text}]({href})"


def _format_missing_evidence_list(missing_evidence: List[Dict[str, Any]]) -> List[str]:
    if not missing_evidence:
        return ["- none"]
    lines = []
    for item in missing_evidence:
        label = item.get("label") or item.get("id") or "Missing evidence"
        location = item.get("bundle_path") or item.get("path") or "not provided"
        kind = item.get("kind") or "evidence"
        note = item.get("note") or "Review before operator acceptance."
        lines.append(f"- {label} ({kind}, {location}): {note}")
    return lines


def _ui_manifest_compatibility(
    *,
    generated_timestamp_utc: str,
    artifact_count: int,
    generated_artifact_count: int,
) -> Dict[str, Any]:
    return {
        "schema_version": UI_MANIFEST_SCHEMA_VERSION,
        "manifest_version": EVIDENCE_BUNDLE_MANIFEST_VERSION,
        "minimum_supported_manifest_version": EVIDENCE_BUNDLE_MANIFEST_VERSION,
        "generated_timestamp_utc": generated_timestamp_utc,
        "required_top_level_fields": list(UI_REQUIRED_TOP_LEVEL_FIELDS),
        "artifact_entry_required_fields": list(UI_ARTIFACT_ENTRY_REQUIRED_FIELDS),
        "optional_field_fallback_policy": (
            "Every optional UI field must render explicit fallback text such as "
            "'not provided', 'n/a', 'UNKNOWN', or 'unavailable'; optional fields must "
            "not render as blank labels."
        ),
        "optional_field_fallbacks": dict(UI_OPTIONAL_FIELD_FALLBACKS),
        "artifact_access": {
            "outside_ui_required": True,
            "expected_formats": [
                "markdown",
                "json",
                "csv",
                "kml",
                "png",
                "manifest",
                "checksum",
                "dashboard",
            ],
            "artifact_count": artifact_count,
            "generated_artifact_count": generated_artifact_count,
            "unavailable_artifact_policy": (
                "Unavailable artifacts render as non-link unavailable labels in the "
                "review UI and Markdown dashboard; they must not be emitted as hrefs."
            ),
            "primary_dashboard": "operator_dashboard.md",
            "visual_review_ui": "operator_review_ui.html",
            "manifest": "manifest.json",
            "checksum": "checksum_manifest.json",
        },
        "ui_behavior": {
            "primary_manifest_source": "manifest.json",
            "fallback_manifest_source": "embedded manifest snapshot",
            "link_policy": "link_when_present_else_unavailable_label",
            "read_only": True,
            "documentation_only": True,
        },
    }


def _format_evidence_bundle_summary(manifest: Dict[str, Any]) -> str:
    completeness = manifest.get("bundle_completeness") or {}
    artifact_completeness = manifest.get("artifact_completeness") or completeness
    regulatory_completeness = manifest.get("regulatory_documentation_completeness") or {}
    review = manifest.get("operator_review") or {}
    missing_evidence = manifest.get("missing_evidence") or []
    freshness = manifest.get("freshness") or {}
    warnings = manifest.get("bundle_warnings") or []
    trust = manifest.get("trust_defensibility") or {}
    weather_status = trust.get("weather_fallback_status") or _weather_fallback_summary(
        manifest.get("weather") or {}
    )
    weather_readiness = (
        manifest.get("weather_evidence_readiness")
        or trust.get("weather_evidence_readiness")
        or weather_status
    )
    regulatory_provenance = (
        manifest.get("regulatory_evidence_provenance")
        or trust.get("regulatory_evidence_provenance")
        or {}
    )
    checksum_readiness = manifest.get("checksum_evidence_readiness") or {}
    ui_compatibility = manifest.get("ui_compatibility") or {}
    artifact_access = ui_compatibility.get("artifact_access") or {}
    robustness_status = trust.get("uncertainty_robustness_status") or _robustness_summary({})
    evidence_warning_summary = trust.get("evidence_warning_summary") or {}
    open_first = _artifact_link("operator_dashboard.md", "operator_dashboard.md")
    completeness_text = (
        f"{_fmt_value(completeness.get('score'), '%')} "
        f"({completeness.get('present_artifacts', 0)} / "
        f"{completeness.get('total_artifacts', 0)} artifacts present)"
    )
    artifact_completeness_text = (
        f"{_fmt_value(artifact_completeness.get('score'), '%')} "
        f"({artifact_completeness.get('present_artifacts', 0)} / "
        f"{artifact_completeness.get('total_artifacts', 0)} artifacts present)"
    )
    regulatory_completeness_text = (
        f"{_fmt_value(regulatory_completeness.get('score'), '%')} "
        f"({regulatory_completeness.get('documented_fields', 0)} / "
        f"{regulatory_completeness.get('total_fields', 0)} fields documented)"
    )
    lines = [
        "# Evidence Bundle Summary",
        "",
        "Human-readable review summary for the operator evidence bundle.",
        "",
        f"Mission: {Path(str(manifest.get('scenario_path', 'scenario.yaml'))).stem}",
        f"Completeness score: {_fmt_value(completeness.get('score'), '%')}",
        f"Artifacts present: {completeness.get('present_artifacts', 0)} / "
        f"{completeness.get('total_artifacts', 0)}",
        f"Missing artifact count: {completeness.get('missing_artifacts', 0)}",
        f"Artifact completeness score: {_fmt_value(artifact_completeness.get('score'), '%')}",
        "Regulatory documentation completeness score: "
        f"{_fmt_value(regulatory_completeness.get('score'), '%')}",
        f"Operator review status: {str(review.get('status', 'draft')).replace('_', ' ')}",
        f"Reviewer: {review.get('reviewer_name') or 'not provided'}",
        f"Review timestamp UTC: {review.get('review_timestamp_utc') or 'not provided'}",
        f"Operator decision: {review.get('operator_decision') or 'not provided'}",
        f"Review notes: {review.get('review_notes') or 'not provided'}",
        f"Generated timestamp UTC: {freshness.get('generated_timestamp_utc') or 'not provided'}",
        f"ORBITAL version: {freshness.get('orbital_version') or 'not provided'}",
        "Scenario SHA-256: "
        f"{((freshness.get('scenario_hash') or {}).get('value')) or 'not provided'}",
        f"Command used: {(freshness.get('command') or {}).get('display') or 'not provided'}",
        f"Manifest version: {manifest.get('manifest_version') or 'legacy / not provided'}",
        f"UI schema version: {ui_compatibility.get('schema_version') or 'not provided'}",
        "",
        "ORBITAL evidence bundles are decision-support packages. Bundle completeness, "
        "review status, review notes, operator decisions, and checksums do not provide "
        "legal approval, LAANC, waivers, authorizations, operational clearance, legal "
        "advice, or permission to fly.",
        "",
        "## Reviewer Snapshot",
        "",
        "| Signal | Value | Reviewer use |",
        "| --- | --- | --- |",
        f"| Open first | {open_first} | Start here for the fastest mission read. |",
        f"| Bundle completeness | {completeness_text} | Confirms expected files are present. |",
        f"| Artifact completeness | {artifact_completeness_text} | Separates file presence from regulatory documentation quality. |",
        "| Regulatory documentation completeness | "
        f"{regulatory_completeness_text} | Shows optional evidence fields captured for review. |",
        f"| Missing evidence | {len(missing_evidence)} item(s) | Review before accepting or archiving the bundle. |",
        f"| Bundle warnings | {len(warnings)} warning(s) | Resolve stale, missing, or mismatched artifacts. |",
        "| Manifest compatibility | "
        f"version {manifest.get('manifest_version') or 'legacy / not provided'}, "
        f"UI schema {ui_compatibility.get('schema_version') or 'not provided'} | "
        "Confirms the UI-facing field contract for local review. |",
        "| Weather evidence | "
        f"{weather_readiness.get('status', 'UNKNOWN')} | "
        f"{weather_readiness.get('operator_action', 'Confirm current field weather before release.')} |",
        "| Regulatory provenance | "
        f"{regulatory_provenance.get('status', 'UNKNOWN')} | "
        f"{regulatory_provenance.get('operator_action', 'Confirm regulatory evidence outside ORBITAL.')} |",
        "| Checksum evidence | "
        f"{checksum_readiness.get('status', 'UNKNOWN')} | "
        f"{checksum_readiness.get('operator_action', 'Run bundle checksum verification before archiving.')} |",
        f"| Robustness | {robustness_status.get('summary', 'No robustness status captured.')} | Review uncertainty assumptions before release. |",
        "| Evidence warnings | "
        f"{evidence_warning_summary.get('summary', f'{len(warnings)} warning(s)')} | "
        "Check stale, missing, or mismatched evidence before archiving. |",
        "| Review status | "
        f"{str(review.get('status', 'draft')).replace('_', ' ')} | Current operator review state. |",
        f"| Operator decision | {review.get('operator_decision') or 'not provided'} | Documentation-only review outcome. |",
        "",
        "## Trust And Defensibility",
        "",
        f"- Sample data / demo scenario note: "
        f"{(trust.get('sample_data_demo_note') or {}).get('note') or 'Verify scenario inputs before operational use.'}",
        f"- Weather evidence readiness: {weather_readiness.get('summary', 'not provided')}",
        f"- Regulatory evidence provenance: {regulatory_provenance.get('summary', 'not provided')}",
        f"- Checksum evidence readiness: {checksum_readiness.get('summary', 'not provided')}",
        f"- Uncertainty / robustness status: "
        f"{robustness_status.get('summary', 'not provided')}",
        f"- Stale or missing evidence status: "
        f"{evidence_warning_summary.get('summary', 'not provided')}",
        "",
        "## Start Here",
        "",
        f"- Operator dashboard: {open_first}",
        "- Primary constraint audit: "
        f"{_artifact_link('inspection_constraint_audit.md', 'inspection_constraint_audit.md')}",
        f"- What-if plan: {_artifact_link('what_if_plan.md', 'what_if_plan.md')}",
        "- Regulatory readiness report: "
        f"{_artifact_link('regulatory_readiness_report.md', 'regulatory_readiness_report.md')}",
        f"- Artifact index: {_artifact_link('artifact_index.md', 'artifact_index.md')}",
        f"- Manifest JSON: {_artifact_link('manifest.json', 'manifest.json')}",
        f"- Checksum manifest: {_artifact_link('checksum_manifest.json', 'checksum_manifest.json')}",
        "",
        "## Recommended Review Flow",
        "",
        "1. Open the operator dashboard for the 10-second mission read.",
        "2. Confirm the top limiting constraint in the primary constraint audit.",
        "3. Review what-if changes if a margin is tight or a mission assumption changes.",
        "4. Confirm regulatory readiness outside ORBITAL.",
        "5. Verify the manifest and checksum manifest before archiving or sharing.",
        "",
        "## UI Manifest Compatibility",
        "",
        "| Contract | Value |",
        "| --- | --- |",
        f"| Manifest version | {manifest.get('manifest_version') or 'legacy / not provided'} |",
        f"| UI schema version | {ui_compatibility.get('schema_version') or 'not provided'} |",
        f"| Required top-level fields | {len(ui_compatibility.get('required_top_level_fields') or [])} expected |",
        f"| Artifact entry fields | {', '.join(ui_compatibility.get('artifact_entry_required_fields') or []) or 'not provided'} |",
        f"| Optional fallback fields | {len(ui_compatibility.get('optional_field_fallbacks') or {})} documented |",
        f"| Outside-UI artifact access | {'yes' if artifact_access.get('outside_ui_required', True) else 'no'} |",
        f"| Unavailable artifact policy | {_markdown_cell(artifact_access.get('unavailable_artifact_policy') or 'Unavailable artifacts render as non-link unavailable labels.')} |",
        "",
        "Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts "
        "remain accessible as files in this evidence bundle. The UI is a convenience "
        "surface, not the source of truth.",
        "",
        "## Missing Evidence",
        "",
    ]
    lines.extend(_format_missing_evidence_list(missing_evidence))
    lines.extend(["", "## Bundle Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(
                f"- {warning.get('kind', 'warning')}: "
                f"{warning.get('message', 'Review evidence bundle before operator acceptance.')}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Regulatory Documentation",
            "",
            f"- Missing optional documentation fields: "
            f"{len((manifest.get('regulatory_evidence_status') or {}).get('missing', []) or [])}",
            f"- Documented optional fields: "
            f"{regulatory_completeness.get('documented_fields', 0)} / "
            f"{regulatory_completeness.get('total_fields', 0)}",
            f"- Approval checklist items: "
            f"{(manifest.get('approval_checklist') or {}).get('item_count', 0)}",
            "",
            "## Review Summary",
            "",
            f"- Review status: {str(review.get('status', 'draft')).replace('_', ' ')}",
            f"- Operator decision: {review.get('operator_decision') or 'not provided'}",
            f"- Reviewer: {review.get('reviewer_name') or 'not provided'}",
            f"- Review timestamp UTC: {review.get('review_timestamp_utc') or 'not provided'}",
            f"- Review notes: {review.get('review_notes') or 'not provided'}",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _artifact_reference(
    manifest: Dict[str, Any],
    artifact_id: str,
    label: str,
    fallback_bundle_path: str,
) -> str:
    for entry in list(manifest.get("artifacts", []) or []) + list(
        manifest.get("generated_artifacts", []) or []
    ):
        if entry.get("id") == artifact_id:
            path = entry.get("bundle_path") or fallback_bundle_path
            if entry.get("present"):
                return _artifact_link(path, label)
            return f"{label} unavailable (missing: {path})"
    return f"{label} unavailable (not listed in manifest)"


def _top_constraint_summary(top: Dict[str, Any]) -> str:
    if not top:
        return "not available"
    margin = top.get("margin") or {}
    margin_value = margin.get("value")
    margin_unit = margin.get("unit") or ""
    label = top.get("label") or top.get("id") or "Constraint"
    status = _constraint_status_label(top.get("status"))
    return f"{label}, {status}, margin {_fmt_value(margin_value, margin_unit)}"


def _dashboard_verdict(
    *,
    mission_status: str,
    regulatory_state: str,
    missing_evidence_count: int,
    warning_count: int,
) -> Dict[str, str]:
    if mission_status != "GO":
        return {
            "label": "MODIFY",
            "meaning": "Modeled constraints do not support release as configured.",
            "next_action": (
                "Modify the route, assumptions, or constraints, then regenerate the "
                "evidence bundle before operator review."
            ),
        }
    if (
        regulatory_state == "OPERATOR_ACTION_REQUIRED"
        or missing_evidence_count > 0
        or warning_count > 0
    ):
        return {
            "label": "REVIEW REQUIRED",
            "meaning": (
                "Modeled feasibility is acceptable, but operator, regulatory, or "
                "evidence review items remain."
            ),
            "next_action": (
                "Complete the listed review items, confirm regulatory readiness outside "
                "ORBITAL, then record the operator decision."
            ),
        }
    return {
        "label": "GO",
        "meaning": "Modeled feasibility and bundle evidence are ready for normal operator review.",
        "next_action": (
            "Proceed to normal operator review, verify checksums, and archive the "
            "evidence bundle."
        ),
    }


def _verdict_derivation(
    *,
    verdict: Dict[str, str],
    mission_status: str,
    regulatory_state: str,
    missing_evidence_count: int,
    warning_count: int,
) -> Dict[str, Any]:
    if mission_status != "GO":
        trigger = "modeled mission status"
        explanation = (
            "The verdict is MODIFY because the modeled mission status is not GO. "
            "Route, assumptions, or constraints should be changed before review."
        )
    elif (
        regulatory_state == "OPERATOR_ACTION_REQUIRED"
        or missing_evidence_count > 0
        or warning_count > 0
    ):
        trigger = "operator review items"
        explanation = (
            "The verdict is REVIEW REQUIRED because modeled feasibility is GO but "
            "regulatory readiness, missing evidence, or bundle warnings still need "
            "operator attention."
        )
    else:
        trigger = "all required review gates clear"
        explanation = (
            "The verdict is GO because modeled mission status is GO, regulatory "
            "readiness does not require action, and no missing evidence or bundle "
            "warnings are recorded."
        )
    inputs = [
        {
            "signal": "Modeled mission status",
            "value": mission_status,
            "effect": "MODIFY if not GO.",
        },
        {
            "signal": "Regulatory readiness",
            "value": regulatory_state,
            "effect": "REVIEW REQUIRED when OPERATOR_ACTION_REQUIRED.",
        },
        {
            "signal": "Missing evidence",
            "value": f"{missing_evidence_count} item(s)",
            "effect": "REVIEW REQUIRED when greater than 0.",
        },
        {
            "signal": "Bundle warnings",
            "value": f"{warning_count} warning(s)",
            "effect": "REVIEW REQUIRED when greater than 0.",
        },
    ]
    return {
        "label": verdict.get("label"),
        "trigger": trigger,
        "explanation": explanation,
        "inputs": inputs,
    }


def _artifact_freshness_rows(
    manifest_entries: List[Dict[str, Any]],
    *,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    priority = {
        "scenario_yaml": 0,
        "constraint_audit_markdown": 1,
        "regulatory_readiness_markdown": 2,
        "what_if_plan_markdown": 3,
        "weather_snapshot": 4,
        "autopilot_mission_csv": 5,
        "mission_review_kml": 6,
        "flight_planning_exports_manifest": 7,
    }
    rows: List[Dict[str, Any]] = []
    for entry in sorted(
        manifest_entries,
        key=lambda item: (
            priority.get(str(item.get("id")), 99),
            str(item.get("label") or item.get("id") or ""),
        ),
    ):
        if entry.get("id") not in priority and len(rows) >= limit:
            continue
        freshness = entry.get("freshness") or {}
        present = bool(entry.get("present"))
        stale = bool(freshness.get("stale_against_scenario"))
        if not present:
            status = "MISSING"
            operator_action = "Regenerate or attach this artifact before operator review."
        elif stale:
            status = "STALE"
            operator_action = "Regenerate this artifact from the current scenario."
        else:
            status = "CURRENT"
            operator_action = "Verify source timestamp and checksum before archiving."
        rows.append(
            {
                "id": entry.get("id"),
                "label": entry.get("label") or entry.get("id") or "Artifact",
                "bundle_path": entry.get("bundle_path") or "not provided",
                "status": status,
                "source_modified_utc": freshness.get("source_modified_utc") or "not provided",
                "bundle_modified_utc": freshness.get("bundle_modified_utc") or "not provided",
                "stale_against_scenario": stale,
                "operator_action": operator_action,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _warning_scan_summary(
    warnings: List[Dict[str, Any]],
    missing_evidence: List[Dict[str, Any]],
    evidence_warning_summary: Dict[str, Any],
) -> Dict[str, Any]:
    stale = int(evidence_warning_summary.get("stale_artifacts", 0) or 0)
    missing_artifacts = int(evidence_warning_summary.get("missing_artifacts", 0) or 0)
    missing_items = int(
        evidence_warning_summary.get("missing_evidence", len(missing_evidence)) or 0
    )
    mismatched = sum(
        1 for warning in warnings if "mismatch" in str(warning.get("kind") or "").lower()
    )
    warning_total = int(evidence_warning_summary.get("bundle_warnings", len(warnings)) or 0)
    return {
        "stale_artifacts": stale,
        "missing_artifacts": missing_artifacts,
        "missing_evidence": missing_items,
        "mismatched_artifacts": mismatched,
        "bundle_warnings": warning_total,
        "summary": (
            f"{stale} stale, {missing_artifacts} missing, {mismatched} mismatched, "
            f"{missing_items} missing evidence item(s), {warning_total} warning(s)"
        ),
    }


def _format_operator_evidence_dashboard(manifest: Dict[str, Any]) -> str:
    audit = manifest.get("constraint_audit") or {}
    regulatory = manifest.get("regulatory_readiness") or {}
    completeness = manifest.get("bundle_completeness") or {}
    regulatory_completeness = manifest.get("regulatory_documentation_completeness") or {}
    review = manifest.get("operator_review") or {}
    trust = manifest.get("trust_defensibility") or {}
    weather_status = trust.get("weather_fallback_status") or _weather_fallback_summary(
        manifest.get("weather") or {}
    )
    weather_readiness = (
        manifest.get("weather_evidence_readiness")
        or trust.get("weather_evidence_readiness")
        or weather_status
    )
    regulatory_provenance = (
        manifest.get("regulatory_evidence_provenance")
        or trust.get("regulatory_evidence_provenance")
        or {}
    )
    checksum_readiness = manifest.get("checksum_evidence_readiness") or {}
    freshness = manifest.get("freshness") or {}
    ui_compatibility = manifest.get("ui_compatibility") or {}
    artifact_access = ui_compatibility.get("artifact_access") or {}
    robustness_status = trust.get("uncertainty_robustness_status") or _robustness_summary({})
    evidence_warning_summary = trust.get("evidence_warning_summary") or {
        "status": "CLEAR" if not manifest.get("bundle_warnings") else "REVIEW REQUIRED",
        "summary": f"{len(manifest.get('bundle_warnings') or [])} bundle warning(s)",
    }
    sample_note = trust.get("sample_data_demo_note") or {}
    assumptions_summary = trust.get("model_assumptions_summary") or []
    limitations_summary = trust.get("known_limitations_summary") or []
    top = audit.get("top_limiting_constraint") or {}
    mission_status = str(audit.get("status") or "unknown").upper()
    mission_risk = str(audit.get("mission_risk") or "unknown").upper()
    regulatory_state = str(
        regulatory.get("readiness_state") or regulatory.get("status") or "unknown"
    ).upper()
    top_summary = _top_constraint_summary(top)
    bundle_completeness_text = (
        f"{_fmt_value(completeness.get('score'), '%')} "
        f"({completeness.get('present_artifacts', 0)} / "
        f"{completeness.get('total_artifacts', 0)} artifacts present)"
    )
    regulatory_completeness_text = (
        f"{_fmt_value(regulatory_completeness.get('score'), '%')} "
        f"({regulatory_completeness.get('documented_fields', 0)} / "
        f"{regulatory_completeness.get('total_fields', 0)} fields documented)"
    )
    missing_evidence = manifest.get("missing_evidence") or []
    warnings = manifest.get("bundle_warnings") or []
    verdict = _dashboard_verdict(
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        missing_evidence_count=len(missing_evidence),
        warning_count=len(warnings),
    )
    verdict_derivation = _verdict_derivation(
        verdict=verdict,
        mission_status=mission_status,
        regulatory_state=regulatory_state,
        missing_evidence_count=len(missing_evidence),
        warning_count=len(warnings),
    )
    verdict_input_lines = [
        "| {signal} | {value} | {effect} |".format(
            signal=_markdown_cell(item.get("signal")),
            value=_markdown_cell(item.get("value")),
            effect=_markdown_cell(item.get("effect")),
        )
        for item in verdict_derivation["inputs"]
    ]
    assumption_snapshot_lines = [
        "| {label} | {assumption} | {operator_check} |".format(
            label=_markdown_cell(item.get("label")),
            assumption=_markdown_cell(item.get("assumption")),
            operator_check=_markdown_cell(item.get("operator_review_note")),
        )
        for item in assumptions_summary[:3]
    ]
    if not assumption_snapshot_lines:
        assumption_snapshot_lines = [
            "| not provided | No model assumptions were captured in the manifest. | "
            "Open the constraint audit and verify scenario inputs before release. |"
        ]
    artifact_freshness_rows = _artifact_freshness_rows(manifest.get("artifacts") or [])
    artifact_freshness_lines = [
        "| {label} | {status} | {source_time} | {bundle_time} | {operator_action} |".format(
            label=_markdown_cell(row.get("label")),
            status=_markdown_cell(row.get("status")),
            source_time=_markdown_cell(row.get("source_modified_utc")),
            bundle_time=_markdown_cell(row.get("bundle_modified_utc")),
            operator_action=_markdown_cell(row.get("operator_action")),
        )
        for row in artifact_freshness_rows
    ]
    warning_scan = _warning_scan_summary(warnings, missing_evidence, evidence_warning_summary)
    mission_name = (
        audit.get("mission_id") or Path(str(manifest.get("scenario_path", "scenario.yaml"))).stem
    )

    primary_links = [
        (
            "Primary constraint audit",
            _artifact_reference(
                manifest,
                "constraint_audit_markdown",
                "inspection_constraint_audit.md",
                "inspection_constraint_audit.md",
            ),
        ),
        (
            "What-if plan",
            _artifact_reference(
                manifest, "what_if_plan_markdown", "what_if_plan.md", "what_if_plan.md"
            ),
        ),
        (
            "Regulatory readiness",
            _artifact_reference(
                manifest,
                "regulatory_readiness_markdown",
                "regulatory_readiness_report.md",
                "regulatory_readiness_report.md",
            ),
        ),
    ]
    evidence_links = [
        (
            "Bundle manifest",
            _artifact_reference(manifest, "manifest_json", "manifest.json", "manifest.json"),
        ),
        (
            "Checksum manifest",
            _artifact_reference(
                manifest,
                "checksum_manifest",
                "checksum_manifest.json",
                "checksum_manifest.json",
            ),
        ),
        (
            "Artifact index",
            _artifact_reference(
                manifest, "artifact_index", "artifact_index.md", "artifact_index.md"
            ),
        ),
    ]
    route_export_links = [
        (
            "Flight path plot",
            _artifact_reference(manifest, "flight_path_plot", "flight_path.png", "flight_path.png"),
        ),
        (
            "Autopilot CSV",
            _artifact_reference(
                manifest,
                "autopilot_mission_csv",
                "autopilot_mission.csv",
                "autopilot_mission.csv",
            ),
        ),
        (
            "Mission review KML",
            _artifact_reference(
                manifest, "mission_review_kml", "mission_review.kml", "mission_review.kml"
            ),
        ),
    ]
    first_artifact_link = _artifact_reference(
        manifest, "operator_dashboard", "operator_dashboard.md", "operator_dashboard.md"
    )
    raw_quick_link_groups = [
        (
            "Raw Markdown",
            [
                _artifact_reference(
                    manifest, "operator_dashboard", "operator_dashboard.md", "operator_dashboard.md"
                ),
                _artifact_reference(
                    manifest,
                    "constraint_audit_markdown",
                    "inspection_constraint_audit.md",
                    "inspection_constraint_audit.md",
                ),
                _artifact_reference(
                    manifest,
                    "what_if_plan_markdown",
                    "what_if_plan.md",
                    "what_if_plan.md",
                ),
                _artifact_reference(
                    manifest,
                    "regulatory_readiness_markdown",
                    "regulatory_readiness_report.md",
                    "regulatory_readiness_report.md",
                ),
                _artifact_reference(
                    manifest,
                    "bundle_summary",
                    "evidence_bundle_summary.md",
                    "evidence_bundle_summary.md",
                ),
                _artifact_reference(
                    manifest, "artifact_index", "artifact_index.md", "artifact_index.md"
                ),
            ],
        ),
        (
            "JSON Evidence",
            [
                _artifact_reference(manifest, "plan_json", "plan.json", "plan.json"),
                _artifact_reference(
                    manifest,
                    "constraint_audit_json",
                    "inspection_constraint_audit.json",
                    "inspection_constraint_audit.json",
                ),
                _artifact_reference(
                    manifest,
                    "what_if_plan_json",
                    "what_if_plan.json",
                    "what_if_plan.json",
                ),
                _artifact_reference(
                    manifest,
                    "regulatory_readiness_json",
                    "regulatory_readiness_report.json",
                    "regulatory_readiness_report.json",
                ),
                _artifact_reference(
                    manifest,
                    "score_breakdown",
                    "score_breakdown.json",
                    "score_breakdown.json",
                ),
                _artifact_reference(
                    manifest,
                    "weather_snapshot",
                    "weather_snapshot.json",
                    "weather_snapshot.json",
                ),
                _artifact_reference(
                    manifest,
                    "robustness_summary",
                    "robustness_summary.json",
                    "robustness_summary.json",
                ),
            ],
        ),
        (
            "CSV / KML",
            [
                _artifact_reference(
                    manifest,
                    "autopilot_mission_csv",
                    "autopilot_mission.csv",
                    "autopilot_mission.csv",
                ),
                _artifact_reference(
                    manifest, "mission_review_kml", "mission_review.kml", "mission_review.kml"
                ),
            ],
        ),
        (
            "Plots",
            [
                _artifact_reference(
                    manifest, "flight_path_plot", "flight_path.png", "flight_path.png"
                )
            ],
        ),
        (
            "Manifest / checksum",
            [
                _artifact_reference(manifest, "manifest_json", "manifest.json", "manifest.json"),
                _artifact_reference(
                    manifest,
                    "checksum_manifest",
                    "checksum_manifest.json",
                    "checksum_manifest.json",
                ),
            ],
        ),
    ]
    raw_quick_link_lines = [
        f"| {group} | {'; '.join(links)} |" for group, links in raw_quick_link_groups
    ]

    lines = [
        "# ORBITAL Operator Evidence Dashboard",
        "",
        f"## Mission Verdict: {verdict['label']}",
        "",
        verdict["meaning"],
        "",
        f"**Next action:** {verdict['next_action']}",
        "",
        "## 30-Second Review Path",
        "",
        "Review order: Verdict -> top constraint -> trust signals -> artifacts -> checksum.",
        "",
        f"**First artifact to open:** {first_artifact_link} (this file).",
        "",
        "| Step | Open / verify |",
        "| --- | --- |",
        f"| Verdict | {verdict['label']} - {verdict['next_action']} |",
        f"| Top constraint | {_markdown_cell(top_summary)} |",
        "| Checksum / freshness | "
        f"{_markdown_cell(checksum_readiness.get('status', 'UNKNOWN'))}; "
        f"generated {_markdown_cell(freshness.get('generated_timestamp_utc', 'not provided'))}; "
        f"manifest version {_markdown_cell(manifest.get('manifest_version', 'legacy / not provided'))} |",
        "| Trust signals | Weather evidence, regulatory provenance, robustness, "
        "model assumptions, and evidence warnings. |",
        "| Artifacts | Open raw Markdown, JSON, CSV, KML, plots, manifest, and checksum links below. |",
        "| Checksum | Run bundle checksum verification before archiving or sharing. |",
        "",
        "## Raw Evidence Quick Links",
        "",
        "| Type | Links |",
        "| --- | --- |",
        *raw_quick_link_lines,
        "",
        "## Manifest Compatibility",
        "",
        "| Contract | Value |",
        "| --- | --- |",
        f"| Manifest version | {manifest.get('manifest_version') or 'legacy / not provided'} |",
        f"| UI schema version | {ui_compatibility.get('schema_version') or 'not provided'} |",
        f"| Required UI-facing top-level fields | {len(ui_compatibility.get('required_top_level_fields') or [])} expected |",
        f"| Optional UI fallbacks | {len(ui_compatibility.get('optional_field_fallbacks') or {})} documented |",
        f"| Outside-UI access | {'yes' if artifact_access.get('outside_ui_required', True) else 'no'} |",
        f"| Unavailable artifact policy | {_markdown_cell(artifact_access.get('unavailable_artifact_policy') or 'Unavailable artifacts render as non-link unavailable labels.')} |",
        "",
        "Markdown, JSON, CSV, KML, PNG, manifest, checksum, and dashboard artifacts "
        "remain accessible outside the UI. Unavailable artifacts are rendered as "
        "unavailable text, not links.",
        "",
        "## Why This Verdict?",
        "",
        verdict_derivation["explanation"],
        "",
        "| Verdict input | Current value | Derivation rule |",
        "| --- | --- | --- |",
        *verdict_input_lines,
        "",
        "## Model Assumptions Snapshot",
        "",
        "| Area | Summary | Operator should verify |",
        "| --- | --- | --- |",
        *assumption_snapshot_lines,
        "",
        "## Mission Card",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Mission | {_markdown_cell(mission_name)} |",
        f"| Verdict | {verdict['label']} |",
        f"| Modeled mission status | {mission_status} |",
        f"| Mission risk | {mission_risk} |",
        f"| Top limiting constraint | {_markdown_cell(top_summary)} |",
        f"| Regulatory readiness | {regulatory_state} |",
        f"| Evidence completeness | {bundle_completeness_text} |",
        f"| Weather evidence status | {_markdown_cell(weather_readiness.get('status', 'UNKNOWN'))} |",
        f"| Weather source | {_markdown_cell(weather_readiness.get('source', 'not provided'))} |",
        f"| Weather timestamp | {_markdown_cell(weather_readiness.get('timestamp_utc', 'not provided'))} |",
        f"| Weather freshness | {_markdown_cell(weather_readiness.get('freshness_status', 'not provided'))} |",
        f"| Regulatory provenance | {_markdown_cell(regulatory_provenance.get('status', 'UNKNOWN'))} |",
        f"| Regulatory date checked | {_markdown_cell(regulatory_provenance.get('date_checked_utc', 'not provided'))} |",
        f"| Regulatory expiration | {_markdown_cell(regulatory_provenance.get('expiration_date', 'not provided'))} |",
        f"| Checksum evidence | {_markdown_cell(checksum_readiness.get('status', 'UNKNOWN'))} |",
        f"| Robustness status | {_markdown_cell(robustness_status.get('summary', 'not provided'))} |",
        f"| Evidence warning status | {_markdown_cell(evidence_warning_summary.get('summary', 'not provided'))} |",
        f"| Missing evidence | {len(missing_evidence)} item(s) |",
        f"| Bundle warnings | {len(warnings)} warning(s) |",
        "",
        "## Decision-Support Boundary",
        "",
        "ORBITAL provides decision support only: not approval, not authorization, "
        "not legal advice, not LAANC, and not operational clearance. The "
        "pilot-in-command and operator retain final responsibility for release.",
        "",
        "## 10-Second Mission Read",
        "",
        "| Signal | Current value | Operator cue |",
        "| --- | --- | --- |",
        f"| Verdict | {verdict['label']} | {verdict['next_action']} |",
        f"| Modeled mission status | {mission_status} | Use as the first feasibility read from the constraint audit. |",
        f"| Mission risk | {mission_risk} | Treat higher risk as a cue for additional operator review. |",
        f"| Top limiting constraint | {_markdown_cell(top_summary)} | Review this constraint before changing or releasing the mission. |",
        f"| Regulatory readiness | {regulatory_state} | Confirm required approvals, waivers, roles, and restrictions outside ORBITAL. |",
        f"| Evidence completeness | {bundle_completeness_text} | Confirm expected artifacts are present before sharing. |",
        "| Regulatory documentation completeness | "
        f"{regulatory_completeness_text} | Confirm optional evidence fields are documented where needed. |",
        f"| Weather evidence | {_markdown_cell(weather_readiness.get('summary', 'not provided'))} | {_markdown_cell(weather_readiness.get('operator_action', 'Confirm current field weather before release.'))} |",
        f"| Regulatory provenance | {_markdown_cell(regulatory_provenance.get('summary', 'not provided'))} | {_markdown_cell(regulatory_provenance.get('operator_action', 'Confirm regulatory evidence outside ORBITAL.'))} |",
        f"| Checksum evidence | {_markdown_cell(checksum_readiness.get('summary', 'not provided'))} | {_markdown_cell(checksum_readiness.get('operator_action', 'Run bundle checksum verification before archiving.'))} |",
        f"| Uncertainty / robustness | {_markdown_cell(robustness_status.get('summary', 'not provided'))} | {_markdown_cell(robustness_status.get('operator_action', 'Review uncertainty assumptions before release.'))} |",
        f"| Evidence warnings | {_markdown_cell(evidence_warning_summary.get('summary', 'not provided'))} | Check stale, missing, or mismatched evidence before archiving. |",
        "",
        "## Trust And Defensibility",
        "",
        "### Sample Data / Demo Scenario Note",
        "",
        sample_note.get("note") or "Verify scenario inputs before operational use.",
        "",
        "### Model Assumptions Summary",
        "",
        "| Area | Summary | Operator check |",
        "| --- | --- | --- |",
    ]
    for item in assumptions_summary[:6]:
        lines.append(
            "| {label} | {assumption} | {operator_check} |".format(
                label=_markdown_cell(item.get("label")),
                assumption=_markdown_cell(item.get("assumption")),
                operator_check=_markdown_cell(item.get("operator_review_note")),
            )
        )
    if not assumptions_summary:
        lines.append(
            "| not provided | No model assumptions were captured in the manifest. | "
            "Open the constraint audit and verify scenario inputs before release. |"
        )
    lines.extend(
        [
            "",
            "### Known Limitations Summary",
            "",
            "| Limitation | Applies | Operator meaning |",
            "| --- | --- | --- |",
        ]
    )
    for item in limitations_summary[:5]:
        lines.append(
            "| {label} | {applies} | {meaning} |".format(
                label=_markdown_cell(item.get("id") or "model limitation"),
                applies="yes" if item.get("applies") else "context",
                meaning=_markdown_cell(item.get("limitation")),
            )
        )
    if not limitations_summary:
        lines.append(
            "| not provided | unknown | Open the constraint audit and review model limitations. |"
        )
    lines.extend(
        [
            "",
            "### Evidence Warnings At A Glance",
            "",
            "| Signal | Value |",
            "| --- | --- |",
            f"| Status | {_markdown_cell(evidence_warning_summary.get('status', 'UNKNOWN'))} |",
            f"| Missing artifacts | {evidence_warning_summary.get('missing_artifacts', len(missing_evidence))} |",
            f"| Stale artifacts | {evidence_warning_summary.get('stale_artifacts', 'not provided')} |",
            f"| Missing evidence items | {evidence_warning_summary.get('missing_evidence', len(missing_evidence))} |",
            f"| Bundle warnings | {evidence_warning_summary.get('bundle_warnings', len(warnings))} |",
            "",
            "### Stale / Missing / Mismatched Evidence Scan",
            "",
            "| Signal | Count |",
            "| --- | --- |",
            f"| Stale artifacts | {warning_scan['stale_artifacts']} |",
            f"| Missing artifacts | {warning_scan['missing_artifacts']} |",
            f"| Mismatched artifacts | {warning_scan['mismatched_artifacts']} |",
            f"| Missing evidence items | {warning_scan['missing_evidence']} |",
            f"| Bundle warnings | {warning_scan['bundle_warnings']} |",
            "",
            f"Scan summary: {warning_scan['summary']}.",
            "",
            "### Artifact Freshness Summary",
            "",
            "| Artifact | Status | Source timestamp | Bundle timestamp | Operator should verify |",
            "| --- | --- | --- | --- | --- |",
            *artifact_freshness_lines,
            "",
            "Open `evidence_bundle_summary.md`, `manifest.json`, and "
            "`checksum_manifest.json` when any warning count is nonzero.",
            "",
            "## Recommended Opening Sequence",
            "",
            "1. Start here with the dashboard.",
            "2. Open the primary constraint audit for feasibility and top-limiter rationale.",
            "3. Open the what-if plan to see how mission changes affect feasibility.",
            "4. Open regulatory readiness to confirm documentation-only action items.",
            "5. Open the manifest, artifact index, and checksum manifest before archiving.",
            "",
            "## Mission Snapshot",
            "",
            f"- Mission: {mission_name}",
            f"- Mission verdict: {verdict['label']}",
            f"- Mission status: {mission_status}",
            f"- Mission risk: {mission_risk}",
            f"- Top limiting constraint: {top_summary}",
            f"- Regulatory readiness: {regulatory_state}",
            f"- Bundle completeness: {bundle_completeness_text}",
            f"- Regulatory documentation completeness: {regulatory_completeness_text}",
            f"- Missing evidence items: {len(missing_evidence)}",
            f"- Bundle warnings: {len(warnings)}",
            "",
            "## Operator Review",
            "",
            f"Review status: {str(review.get('status', 'draft')).replace('_', ' ')}",
            f"Reviewer name: {review.get('reviewer_name') or 'not provided'}",
            f"Review timestamp UTC: {review.get('review_timestamp_utc') or 'not provided'}",
            f"Operator decision: {review.get('operator_decision') or 'not provided'}",
            f"Review notes: {review.get('review_notes') or 'not provided'}",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Review status | {str(review.get('status', 'draft')).replace('_', ' ')} |",
            f"| Reviewer name | {review.get('reviewer_name') or 'not provided'} |",
            "| Review timestamp UTC | " f"{review.get('review_timestamp_utc') or 'not provided'} |",
            f"| Operator decision | {review.get('operator_decision') or 'not provided'} |",
            f"| Review notes | {review.get('review_notes') or 'not provided'} |",
            "",
            "Review fields are documentation-only records; they do not change release "
            "authority.",
            "",
            "## Artifact Shortcuts",
            "",
            "### Feasibility And Decision Support",
            "",
            "| Artifact | Link |",
            "| --- | --- |",
        ]
    )
    for label, link in primary_links:
        lines.append(f"| {_markdown_cell(label)} | {link} |")

    lines.extend(
        [
            "",
            "### Evidence Package",
            "",
            "| Artifact | Link |",
            "| --- | --- |",
        ]
    )
    for label, link in evidence_links:
        lines.append(f"| {_markdown_cell(label)} | {link} |")

    lines.extend(
        [
            "",
            "### Route, Export, And Field-Use Artifacts",
            "",
            "| Artifact | Link |",
            "| --- | --- |",
        ]
    )
    for label, link in route_export_links:
        lines.append(f"| {_markdown_cell(label)} | {link} |")

    lines.extend(["", "## Missing Evidence", ""])
    lines.extend(_format_missing_evidence_list(missing_evidence))
    lines.extend(["", "## Bundle Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(
                f"- {warning.get('kind', 'warning')}: "
                f"{warning.get('message', 'Review evidence bundle before operator acceptance.')}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Operator Actions",
            "",
            f"- {verdict['next_action']}",
            "- Review the primary constraint audit and top limiting constraint.",
            "- Review the what-if plan if any constraint margin is tight.",
            "- Verify bundle completeness, manifest, and checksum manifest before archiving.",
            "- Record reviewer, timestamp, notes, and operator decision in scenario metadata "
            "when appropriate.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_artifact_index(manifest: Dict[str, Any]) -> str:
    expected_artifacts = manifest.get("artifacts", []) or []
    generated_artifacts = manifest.get("generated_artifacts", []) or []
    expected_present = sum(1 for entry in expected_artifacts if entry.get("present"))
    expected_missing = max(0, len(expected_artifacts) - expected_present)
    lines = [
        "# Evidence Bundle Artifact Index",
        "",
        "Links are relative to this evidence bundle folder. Open "
        "[operator_dashboard.md](operator_dashboard.md) first, then use this index "
        "when you need a specific artifact.",
        "",
        "## Open First",
        "",
        "[operator_dashboard.md](operator_dashboard.md) is the first review surface. "
        "It summarizes the mission verdict, risk, top limiting constraint, regulatory "
        "readiness, evidence completeness, and next operator action.",
        "",
        "## Review Path",
        "",
        "| Step | Purpose | Artifact |",
        "| ---: | --- | --- |",
        "| 1 | Mission verdict and next action | [operator_dashboard.md](operator_dashboard.md) |",
        "| 2 | Feasibility and top limiting constraint | [inspection_constraint_audit.md](inspection_constraint_audit.md) |",
        "| 3 | What-if comparison | [what_if_plan.md](what_if_plan.md) |",
        "| 4 | Documentation-only regulatory review | [regulatory_readiness_report.md](regulatory_readiness_report.md) |",
        "| 5 | Bundle completeness and review metadata | [evidence_bundle_summary.md](evidence_bundle_summary.md) |",
        "| 6 | Archive and checksum verification | [manifest.json](manifest.json), [checksum_manifest.json](checksum_manifest.json) |",
        "",
        "## Artifact Status Summary",
        "",
        f"- Expected artifacts included: {expected_present} / {len(expected_artifacts)}",
        f"- Expected artifacts missing: {expected_missing}",
        f"- Generated bundle index artifacts: {len(generated_artifacts)}",
        "",
        "## Recommended Opening Order",
        "",
        "1. [operator_dashboard.md](operator_dashboard.md)",
        "2. [inspection_constraint_audit.md](inspection_constraint_audit.md)",
        "3. [what_if_plan.md](what_if_plan.md)",
        "4. [regulatory_readiness_report.md](regulatory_readiness_report.md)",
        "5. [manifest.json](manifest.json)",
        "6. [checksum_manifest.json](checksum_manifest.json)",
        "",
        "## All Bundle Artifacts",
        "",
        "| Artifact | Status | Link | Type |",
        "| --- | --- | --- | --- |",
    ]
    for entry in manifest.get("artifacts", []) or []:
        status = "included" if entry.get("present") else "missing"
        lines.append(
            "| {label} | {status} | {link} | expected |".format(
                label=_markdown_cell(entry.get("label") or entry.get("id")),
                status=status,
                link=(
                    _artifact_link(entry.get("bundle_path"))
                    if entry.get("present")
                    else _markdown_cell(entry.get("bundle_path"))
                ),
            )
        )
    for entry in manifest.get("generated_artifacts", []) or []:
        lines.append(
            "| {label} | included | {link} | generated |".format(
                label=_markdown_cell(entry.get("label") or entry.get("id")),
                link=_artifact_link(entry.get("bundle_path")),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _bundle_checksum_entries(bundle_dir: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file() or path.name == "checksum_manifest.json":
            continue
        sha256 = _file_sha256(path)
        size = _file_size(path)
        if sha256 is None or size is None:
            continue
        entries.append(
            {
                "bundle_path": str(path.relative_to(bundle_dir)).replace("\\", "/"),
                "sha256": sha256,
                "size_bytes": size,
            }
        )
    return entries


def verify_evidence_bundle_checksums(bundle_dir: Path) -> Dict[str, Any]:
    """Verify evidence bundle checksums and freshness metadata."""
    bundle_dir = Path(bundle_dir)
    checksum_path = bundle_dir / "checksum_manifest.json"
    manifest_path = bundle_dir / "manifest.json"
    checksum_manifest = _read_json_mapping(checksum_path)
    manifest = _read_json_mapping(manifest_path)
    warnings: List[Dict[str, Any]] = []
    missing_files: List[Dict[str, Any]] = []
    mismatched_files: List[Dict[str, Any]] = []
    size_mismatches: List[Dict[str, Any]] = []
    checksum_manifest_stale = False

    if not checksum_manifest:
        warnings.append(
            {
                "id": "missing_checksum_manifest",
                "kind": "missing_artifact",
                "severity": "warning",
                "bundle_path": "checksum_manifest.json",
                "message": "Checksum manifest is missing or unreadable.",
            }
        )
    elif checksum_path.exists() and manifest_path.exists():
        checksum_modified = _file_modified_timestamp(checksum_path)
        manifest_modified = _file_modified_timestamp(manifest_path)
        checksum_manifest_stale = bool(
            checksum_modified is not None
            and manifest_modified is not None
            and checksum_modified < manifest_modified
        )
        if checksum_manifest_stale:
            warnings.append(
                {
                    "id": "stale_checksum_manifest",
                    "kind": "checksum_evidence_stale",
                    "severity": "warning",
                    "bundle_path": "checksum_manifest.json",
                    "message": (
                        "Checksum manifest is older than manifest.json; regenerate or "
                        "rerun bundle checksum verification before archiving."
                    ),
                }
            )
    for entry in checksum_manifest.get("files", []) or []:
        bundle_path = str(entry.get("bundle_path") or "").strip()
        if not bundle_path:
            continue
        path = bundle_dir / bundle_path
        if not path.exists():
            record = {
                "bundle_path": bundle_path,
                "expected_sha256": entry.get("sha256"),
                "message": "Checksummed bundle file is missing.",
            }
            missing_files.append(record)
            warnings.append(
                {
                    "id": f"missing_checksum_file_{bundle_path}",
                    "kind": "missing_artifact",
                    "severity": "warning",
                    "bundle_path": bundle_path,
                    "message": record["message"],
                }
            )
            continue
        actual_sha = _file_sha256(path)
        if actual_sha != entry.get("sha256"):
            record = {
                "bundle_path": bundle_path,
                "expected_sha256": entry.get("sha256"),
                "actual_sha256": actual_sha,
                "message": "Bundle file checksum does not match checksum_manifest.json.",
            }
            mismatched_files.append(record)
            warnings.append(
                {
                    "id": f"checksum_mismatch_{bundle_path}",
                    "kind": "checksum_mismatch",
                    "severity": "warning",
                    "bundle_path": bundle_path,
                    "message": record["message"],
                }
            )
        actual_size = _file_size(path)
        if actual_size != entry.get("size_bytes"):
            record = {
                "bundle_path": bundle_path,
                "expected_size_bytes": entry.get("size_bytes"),
                "actual_size_bytes": actual_size,
                "message": "Bundle file size does not match checksum_manifest.json.",
            }
            size_mismatches.append(record)
            warnings.append(
                {
                    "id": f"size_mismatch_{bundle_path}",
                    "kind": "checksum_mismatch",
                    "severity": "warning",
                    "bundle_path": bundle_path,
                    "message": record["message"],
                }
            )

    expected_scenario_hash = ((manifest.get("freshness") or {}).get("scenario_hash") or {}).get(
        "value"
    )
    actual_scenario_hash = _file_sha256(bundle_dir / "scenario.yaml")
    scenario_metadata_ok = bool(
        expected_scenario_hash
        and actual_scenario_hash
        and expected_scenario_hash == actual_scenario_hash
    )
    if (
        expected_scenario_hash
        and actual_scenario_hash
        and expected_scenario_hash != actual_scenario_hash
    ):
        warnings.append(
            {
                "id": "scenario_hash_mismatch",
                "kind": "scenario_metadata_mismatch",
                "severity": "warning",
                "bundle_path": "scenario.yaml",
                "expected_sha256": expected_scenario_hash,
                "actual_sha256": actual_scenario_hash,
                "message": (
                    "Bundled scenario.yaml does not match the scenario hash recorded in "
                    "manifest freshness metadata."
                ),
            }
        )
    elif expected_scenario_hash and not actual_scenario_hash:
        warnings.append(
            {
                "id": "missing_scenario_yaml",
                "kind": "missing_artifact",
                "severity": "warning",
                "bundle_path": "scenario.yaml",
                "message": "Bundled scenario.yaml is missing or unreadable.",
            }
        )

    manifest_artifact_warnings = []
    for entry in manifest.get("artifacts", []) or []:
        bundle_path = str(entry.get("bundle_path") or "").strip()
        if entry.get("present") and bundle_path and not (bundle_dir / bundle_path).exists():
            manifest_artifact_warnings.append(
                {
                    "id": f"missing_manifest_artifact_{entry.get('id')}",
                    "kind": "missing_artifact",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "bundle_path": bundle_path,
                    "message": "Manifest marks artifact present, but the bundled file is missing.",
                }
            )
        if (entry.get("freshness") or {}).get("stale_against_scenario"):
            manifest_artifact_warnings.append(
                {
                    "id": f"stale_manifest_artifact_{entry.get('id')}",
                    "kind": "stale_artifact",
                    "severity": "warning",
                    "artifact_id": entry.get("id"),
                    "bundle_path": bundle_path,
                    "message": "Manifest marks artifact as older than the scenario file.",
                }
            )
    warnings.extend(manifest_artifact_warnings)

    checksum_ok = (
        not missing_files
        and not mismatched_files
        and not size_mismatches
        and not checksum_manifest_stale
    )
    metadata_ok = scenario_metadata_ok and not manifest_artifact_warnings
    return {
        "kind": "evidence_bundle_verification",
        "bundle_dir": str(bundle_dir),
        "ok": bool(checksum_manifest) and checksum_ok and metadata_ok,
        "checksum_ok": checksum_ok,
        "metadata_ok": metadata_ok,
        "scenario_metadata_ok": scenario_metadata_ok,
        "checked_files": len(checksum_manifest.get("files", []) or []),
        "missing_files": missing_files,
        "mismatched_files": mismatched_files,
        "size_mismatches": size_mismatches,
        "warnings": warnings,
    }


def export_operator_evidence_bundle(
    out_dir: Path,
    scenario_path: Path,
    *,
    bundle_dir_name: str = "operator_evidence_bundle",
    cfg: Optional[Dict[str, Any]] = None,
    command_used: Optional[Any] = None,
    generated_timestamp_utc: Optional[Any] = None,
) -> Dict[str, Any]:
    """Copy operator-facing BVLOS evidence artifacts into one review bundle."""
    out_dir = Path(out_dir)
    scenario_path = Path(scenario_path)
    bundle_dir = out_dir / bundle_dir_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    generated_timestamp_utc = normalize_generated_timestamp(generated_timestamp_utc)
    scenario_sha256 = _file_sha256(scenario_path)
    scenario_modified_ts = _file_modified_timestamp(scenario_path)
    weather = _weather_metadata(cfg)
    weather_evidence_readiness = _weather_evidence_readiness(
        weather,
        generated_timestamp_utc=generated_timestamp_utc,
    )
    output_cfg = (cfg or {}).get("output", {}) or {}
    flight_exports_enabled = bool(
        output_cfg.get("export_flight_planning_exports", False)
        or output_cfg.get("export_autopilot_csv", False)
        or output_cfg.get("export_kml", False)
    )
    regulatory = _regulatory_metadata(cfg)
    readiness_report = _read_json_mapping(out_dir / "regulatory_readiness_report.json")
    readiness_evidence = readiness_report.get("regulatory_evidence")
    regulatory_evidence = (
        readiness_evidence
        if isinstance(readiness_evidence, dict)
        else _regulatory_evidence_fields(regulatory)
    )
    regulatory_evidence_provenance = _regulatory_evidence_provenance(
        regulatory,
        regulatory_evidence,
        generated_timestamp_utc=generated_timestamp_utc,
    )
    regulatory_evidence_status = _regulatory_evidence_status(regulatory, regulatory_evidence)
    regulatory_documentation_completeness = _regulatory_documentation_completeness(
        regulatory_evidence_status
    )
    approval_checklist = _approval_checklist_summary(
        readiness_report,
        regulatory=regulatory,
        cfg=cfg,
    )

    artifacts: List[Dict[str, Any]] = [
        {
            "id": "scenario_yaml",
            "label": "Scenario YAML",
            "source": scenario_path,
            "bundle_name": "scenario.yaml",
        },
        {
            "id": "plan_json",
            "label": "Plan JSON",
            "source": out_dir / "plan.json",
            "bundle_name": "plan.json",
        },
        {
            "id": "constraint_audit_markdown",
            "label": "Primary constraint-audit report",
            "source": out_dir / "inspection_constraint_audit.md",
            "bundle_name": "inspection_constraint_audit.md",
        },
        {
            "id": "constraint_audit_json",
            "label": "Constraint audit JSON",
            "source": out_dir / "inspection_constraint_audit.json",
            "bundle_name": "inspection_constraint_audit.json",
        },
        {
            "id": "regulatory_readiness_json",
            "label": "Regulatory readiness JSON",
            "source": out_dir / "regulatory_readiness_report.json",
            "bundle_name": "regulatory_readiness_report.json",
        },
        {
            "id": "regulatory_readiness_markdown",
            "label": "Regulatory readiness report",
            "source": out_dir / "regulatory_readiness_report.md",
            "bundle_name": "regulatory_readiness_report.md",
        },
        {
            "id": "what_if_plan_markdown",
            "label": "What-if planning report",
            "source": out_dir / "what_if_plan.md",
            "bundle_name": "what_if_plan.md",
        },
        {
            "id": "what_if_plan_json",
            "label": "What-if planning JSON",
            "source": out_dir / "what_if_plan.json",
            "bundle_name": "what_if_plan.json",
        },
        {
            "id": "score_breakdown",
            "label": "Score breakdown",
            "source": out_dir / "score.json",
            "bundle_name": "score.json",
        },
        {
            "id": "flight_path_plot",
            "label": "Flight path plot",
            "source": out_dir / "flight_path.png",
            "bundle_name": "flight_path.png",
        },
        {
            "id": "robustness_summary",
            "label": "Robustness summary",
            "source": out_dir / "robustness.json",
            "bundle_name": "robustness.json",
        },
        {
            "id": "go_no_go_memo",
            "label": "Plain-English go/no-go memo",
            "source": out_dir / "operator_memo.md",
            "bundle_name": "operator_memo.md",
        },
    ]
    if weather:
        artifacts.append(
            {
                "id": "weather_snapshot",
                "label": "Weather snapshot",
                "source": out_dir / "weather.json",
                "bundle_name": "weather.json",
            }
        )
    if flight_exports_enabled:
        if bool(output_cfg.get("export_autopilot_csv", True)):
            artifacts.append(
                {
                    "id": "autopilot_mission_csv",
                    "label": "Autopilot mission CSV",
                    "source": out_dir / "autopilot_mission.csv",
                    "bundle_name": "autopilot_mission.csv",
                }
            )
        if bool(output_cfg.get("export_kml", True)):
            artifacts.append(
                {
                    "id": "mission_review_kml",
                    "label": "Mission review KML",
                    "source": out_dir / "mission_review.kml",
                    "bundle_name": "mission_review.kml",
                }
            )
        artifacts.extend(
            [
                {
                    "id": "flight_planning_exports_manifest",
                    "label": "Flight-planning exports manifest",
                    "source": out_dir / "flight_planning_exports.json",
                    "bundle_name": "flight_planning_exports.json",
                },
                {
                    "id": "flight_planning_exports_readme",
                    "label": "Flight-planning exports README",
                    "source": out_dir / "flight_planning_exports.md",
                    "bundle_name": "flight_planning_exports.md",
                },
            ]
        )

    for artifact in artifacts:
        if artifact["id"] == "scenario_yaml":
            continue
        source = Path(artifact["source"])
        if source.exists() and _path_is_inside(source, out_dir):
            _touch_generated_file(source, generated_timestamp_utc)

    manifest_entries: List[Dict[str, Any]] = []
    for artifact in artifacts:
        source = Path(artifact["source"])
        destination = bundle_dir / str(artifact["bundle_name"])
        present = source.exists()
        if present:
            copy2(source, destination)

        manifest_entries.append(
            {
                "id": artifact["id"],
                "label": artifact["label"],
                "source": _portable_path_text(source),
                "bundle_path": str(destination.relative_to(bundle_dir)),
                "present": present,
                "artifact_format": _artifact_format(destination.name),
                "opens_outside_ui": True,
                "ui_link_behavior": "link_when_present_else_unavailable_label",
                "freshness": _artifact_freshness_metadata(
                    source=source,
                    destination=destination,
                    present=present,
                    scenario_modified_ts=scenario_modified_ts,
                ),
            }
        )

    missing = [entry["id"] for entry in manifest_entries if not entry["present"]]
    missing_ids = set(missing)
    bundle_completeness = _bundle_completeness(manifest_entries)
    bundle_warnings = _bundle_warnings(
        manifest_entries,
        scenario_sha256=scenario_sha256,
    ) + _operational_evidence_warnings(
        weather_readiness=weather_evidence_readiness,
        regulatory_provenance=regulatory_evidence_provenance,
        manifest_entries=manifest_entries,
    )
    missing_evidence = _bundle_missing_evidence(
        manifest_entries,
        regulatory_evidence_status,
    )
    operator_review = _evidence_bundle_review_metadata(
        cfg,
        artifacts_complete=not missing,
        missing_regulatory_evidence=regulatory_evidence_status.get("operator_attention_missing", [])
        or [],
    )
    generated_artifacts = _generated_bundle_artifacts()
    constraint_audit = _read_json_mapping(out_dir / "inspection_constraint_audit.json")
    trust_defensibility = _trust_defensibility_summary(
        constraint_audit=constraint_audit,
        manifest_entries=manifest_entries,
        missing_evidence=missing_evidence,
        bundle_warnings=bundle_warnings,
        weather=weather,
        weather_readiness=weather_evidence_readiness,
        regulatory_provenance=regulatory_evidence_provenance,
        scenario_path=scenario_path,
    )
    freshness_metadata = {
        "generated_timestamp_utc": generated_timestamp_utc,
        "orbital_version": _orbital_version(),
        "scenario_path": _portable_path_text(scenario_path),
        "scenario_hash": {
            "algorithm": "sha256",
            "value": scenario_sha256,
        },
        "scenario_modified_utc": _file_modified_utc(scenario_path),
        "command": _command_metadata(command_used),
        "metadata_note": (
            "Freshness metadata supports evidence review. It does not provide flight "
            "approval, authorization, legal advice, or operational clearance."
        ),
    }
    review_metadata = {
        "schema_version": 1,
        "status": operator_review.get("status"),
        "requested_status": operator_review.get("requested_status"),
        "reviewer_name": operator_review.get("reviewer_name"),
        "review_timestamp_utc": operator_review.get("review_timestamp_utc"),
        "review_notes": operator_review.get("review_notes"),
        "operator_decision": operator_review.get("operator_decision"),
        "documentation_only": True,
        "notice": operator_review.get("notice"),
    }
    ui_compatibility = _ui_manifest_compatibility(
        generated_timestamp_utc=generated_timestamp_utc,
        artifact_count=len(manifest_entries),
        generated_artifact_count=len(generated_artifacts),
    )
    manifest: Dict[str, Any] = {
        "kind": "operator_evidence_bundle",
        "manifest_version": EVIDENCE_BUNDLE_MANIFEST_VERSION,
        "ui_manifest_version": UI_MANIFEST_SCHEMA_VERSION,
        "ui_compatibility": ui_compatibility,
        "bundle_dir": _portable_path_text(bundle_dir),
        "scenario_path": _portable_path_text(scenario_path),
        "complete": not missing,
        "missing": missing,
        "bundle_completeness_score": bundle_completeness["score"],
        "bundle_completeness": bundle_completeness,
        "artifact_completeness": bundle_completeness,
        "regulatory_documentation_completeness": regulatory_documentation_completeness,
        "missing_evidence": missing_evidence,
        "bundle_warnings": bundle_warnings,
        "operator_review": operator_review,
        "review_metadata": review_metadata,
        "freshness": freshness_metadata,
        "weather": (
            {
                "source": weather.get("source"),
                "provider": weather.get("provider"),
                "timestamp_utc": weather.get("timestamp_utc"),
                "fallback_used": weather.get("fallback_used"),
                "fallback_reason": weather.get("fallback_reason"),
                "live_fetch_enabled": weather.get("live_fetch_enabled"),
                "applied_to_wind": weather.get("applied_to_wind"),
            }
            if weather
            else {}
        ),
        "weather_evidence_readiness": weather_evidence_readiness,
        "regulatory_evidence_provenance": regulatory_evidence_provenance,
        "checksum_evidence_readiness": _checksum_evidence_readiness(generated_timestamp_utc),
        "flight_planning_exports_enabled": flight_exports_enabled,
        "regulatory_metadata": regulatory,
        "constraint_audit": {
            "mission_id": constraint_audit.get("mission_id"),
            "status": constraint_audit.get("status"),
            "mission_risk": constraint_audit.get("mission_risk"),
            "top_limiting_constraint": constraint_audit.get("top_limiting_constraint"),
        },
        "trust_defensibility": trust_defensibility,
        "regulatory_readiness": {
            "status": readiness_report.get("status"),
            "readiness_state": readiness_report.get("readiness_state"),
            "documentation_only": readiness_report.get("documentation_only", True),
            "not_legal_approval": readiness_report.get("not_legal_approval", True),
        },
        "regulatory_evidence": regulatory_evidence,
        "regulatory_evidence_status": regulatory_evidence_status,
        "approval_checklist": approval_checklist,
        "artifacts": manifest_entries,
        "generated_artifacts": generated_artifacts,
        "checksum_manifest": {
            "algorithm": "sha256",
            "bundle_path": "checksum_manifest.json",
            "excludes": ["checksum_manifest.json"],
        },
        "documentation_only_notice": (
            "This bundle supports operator review and audit evidence only. ORBITAL does not "
            "provide LAANC, waivers, authorizations, legal approval, autopilot control, or "
            "operational clearance."
        ),
    }
    manifest_path = bundle_dir / "manifest.json"
    write_strict_json(manifest_path, manifest)
    _touch_generated_file(manifest_path, generated_timestamp_utc)

    readme_lines = [
        "# ORBITAL Operator Evidence Bundle",
        "",
        "This folder collects the artifacts an operator can review before a BVLOS "
        "inspection mission.",
        "",
        "ORBITAL is preflight decision support and audit evidence. It is not a LAANC "
        "provider, autopilot, waiver system, legal approval system, or operational "
        "clearance system.",
        "",
        "Regulatory metadata, authorization references, approval checklist items, and "
        "evidence fields in this bundle are documentation-only. They support operator "
        "review; they are not proof of authorization, legal approval, LAANC, waiver, or "
        "operational clearance.",
        "",
        "Start with `operator_dashboard.md`, then use `artifact_index.md` to open "
        "individual artifacts. `evidence_bundle_summary.md` summarizes completeness, "
        "and `checksum_manifest.json` provides lightweight SHA-256 checksums for files "
        "in this bundle. For a local read-only browser view, open "
        "`operator_review_ui.html`; the Markdown, JSON, CSV, KML, PNG, manifest, "
        "checksum, and dashboard artifacts remain accessible outside the UI.",
        "",
        "## Open This First",
        "",
        "`operator_dashboard.md` is the first file to open. It gives the mission verdict, "
        "mission risk, top limiting constraint, regulatory readiness, evidence "
        "completeness, and next operator action before the reviewer drills into details.",
        "Open `operator_review_ui.html` for the same operator review signals in a "
        "lightweight local web UI. Opening or reviewing that page does not approve, "
        "authorize, clear, or legally validate a mission.",
        "",
        "## How To Review This Bundle",
        "",
        "Start with the dashboard, then open the constraint audit for feasibility and "
        "top-limiter rationale, the what-if report for mission tradeoffs, and the "
        "regulatory readiness report for documentation-only action items. Use the "
        "evidence summary to check missing evidence, warnings, reviewer metadata, and "
        "operator decision status.",
        "",
        "## How To Archive This Bundle",
        "",
        "Archive the full `operator_evidence_bundle/` folder after review. Keep "
        "`manifest.json`, `checksum_manifest.json`, the scenario YAML, and all linked "
        "artifacts together so a later reviewer can verify the files came from the same "
        "scenario and generation run.",
        "",
        "## Completeness And Verification",
        "",
        "Artifact completeness reports whether expected bundle files are present. "
        "Regulatory documentation completeness is reported separately because optional "
        "regulatory evidence fields are documentation aids, not generated artifact "
        "failures or approvals. `checksum_manifest.json` records lightweight SHA-256 "
        "checksums; run `python -m mission_framework.cli bundle-verify <bundle>` to "
        "check whether archived files still match the bundle manifest.",
        f"Manifest version: {EVIDENCE_BUNDLE_MANIFEST_VERSION}. UI schema version: "
        f"{UI_MANIFEST_SCHEMA_VERSION}. Unavailable artifacts render as unavailable "
        "labels rather than links.",
        "",
        "Recommended opening order:",
        "",
        "1. `operator_dashboard.md` for the 10-second mission read.",
        "2. `inspection_constraint_audit.md` for feasibility and top-limiter rationale.",
        "3. `what_if_plan.md` for improvement options.",
        "4. `regulatory_readiness_report.md` for documentation-only regulatory review.",
        "5. `manifest.json` and `checksum_manifest.json` for archive checks.",
        "",
        "## Bundle Summary",
        "",
        f"- Completeness score: {_fmt_value(bundle_completeness['score'], '%')}",
        f"- Artifact completeness score: {_fmt_value(bundle_completeness['score'], '%')}",
        "- Regulatory documentation completeness score: "
        f"{_fmt_value(regulatory_documentation_completeness['score'], '%')}",
        f"- Missing evidence items: {len(missing_evidence)}",
        f"- Bundle warnings: {len(bundle_warnings)}",
        f"- Operator review status: {operator_review['status'].replace('_', ' ')}",
        f"- Reviewer: {operator_review.get('reviewer_name') or 'not provided'}",
        f"- Review timestamp UTC: "
        f"{operator_review.get('review_timestamp_utc') or 'not provided'}",
        f"- Operator decision: {operator_review.get('operator_decision') or 'not provided'}",
        f"- Review notes: {operator_review.get('review_notes') or 'not provided'}",
        "",
        "## Contents",
        "",
    ]
    for entry in manifest_entries:
        status = "included" if entry["present"] else "missing"
        readme_lines.append(f"- {entry['label']}: `{entry['bundle_path']}` ({status})")

    missing_evidence = regulatory_evidence_status["missing"]
    missing_evidence_text = (
        ", ".join(item["label"] for item in missing_evidence) if missing_evidence else "none"
    )
    readme_lines.extend(
        [
            "",
            "## Regulatory Readiness",
            "",
            "- Readiness report JSON: "
            f"{'missing' if 'regulatory_readiness_json' in missing_ids else 'included'}",
            "- Readiness report Markdown: "
            f"{'missing' if 'regulatory_readiness_markdown' in missing_ids else 'included'}",
            "- Approval checklist source: "
            f"{approval_checklist.get('source_artifact') or 'not provided'}",
            f"- Approval checklist items: {approval_checklist['item_count']}",
            f"- Missing documentation-only evidence fields: {missing_evidence_text}",
            "- Documentation-only status: regulatory evidence and checklist items are "
            "operator review aids, not approvals.",
        ]
    )
    if approval_checklist["items"]:
        readme_lines.extend(["", "## Approval Checklist", ""])
        for item in approval_checklist["items"]:
            label = item.get("label") or item.get("id") or "Checklist item"
            readme_lines.append(f"- [ ] {label}")
    if weather:
        readme_lines.extend(
            [
                "",
                "## Weather / Live Evidence Readiness",
                "",
                f"- Status: {weather_evidence_readiness.get('status') or 'not provided'}",
                f"- Mode: {weather_evidence_readiness.get('mode') or 'not provided'}",
                f"- Source: {weather_evidence_readiness.get('source') or 'not provided'}",
                f"- Provider: {weather_evidence_readiness.get('provider') or 'not provided'}",
                "- Timestamp: "
                f"{weather_evidence_readiness.get('timestamp_utc') or 'not provided'}",
                "- Freshness: "
                f"{weather_evidence_readiness.get('freshness_status') or 'not provided'}",
                "- Operator action: "
                f"{weather_evidence_readiness.get('operator_action') or 'not provided'}",
                "- Live provider hook: documentation-only; live weather integration can "
                "populate this field but is not required.",
                "",
                "## Regulatory Evidence Provenance",
                "",
                f"- Status: {regulatory_evidence_provenance.get('status') or 'not provided'}",
                f"- Source: {regulatory_evidence_provenance.get('source') or 'not provided'}",
                "- Date checked: "
                f"{regulatory_evidence_provenance.get('date_checked_utc') or 'not provided'}",
                "- Expiration: "
                f"{regulatory_evidence_provenance.get('expiration_date') or 'not provided'}",
                f"- Authority: {regulatory_evidence_provenance.get('authority') or 'not provided'}",
                "- Operator confirmation status: "
                f"{regulatory_evidence_provenance.get('operator_confirmation_status') or 'not provided'}",
                "- Operator action: "
                f"{regulatory_evidence_provenance.get('operator_action') or 'not provided'}",
                "- Documentation-only: ORBITAL does not grant approval, authorization, "
                "LAANC, legal advice, or operational clearance.",
            ]
        )
    if flight_exports_enabled:
        readme_lines.extend(
            [
                "",
                "## Flight-Planning Exports",
                "",
                FLIGHT_PLANNING_EXPORT_NOTICE,
            ]
        )

    generated_bundle_paths = [
        bundle_dir / "README.md",
        bundle_dir / "evidence_bundle_summary.md",
        bundle_dir / "operator_dashboard.md",
        bundle_dir / "artifact_index.md",
        bundle_dir / "operator_review_ui.html",
    ]
    generated_bundle_paths[0].write_text(
        "\n".join(readme_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    generated_bundle_paths[1].write_text(
        _format_evidence_bundle_summary(manifest),
        encoding="utf-8",
    )
    generated_bundle_paths[2].write_text(
        _format_operator_evidence_dashboard(manifest),
        encoding="utf-8",
    )
    generated_bundle_paths[3].write_text(
        _format_artifact_index(manifest),
        encoding="utf-8",
    )
    generated_bundle_paths[4].write_text(
        format_operator_review_ui_html(manifest),
        encoding="utf-8",
    )
    for generated_path in generated_bundle_paths:
        _touch_generated_file(generated_path, generated_timestamp_utc)
    checksum_payload = {
        "kind": "evidence_bundle_checksum_manifest",
        "algorithm": "sha256",
        "excludes": ["checksum_manifest.json"],
        "files": _bundle_checksum_entries(bundle_dir),
    }
    checksum_path = bundle_dir / "checksum_manifest.json"
    write_strict_json(checksum_path, checksum_payload)
    _touch_generated_file(checksum_path, generated_timestamp_utc)
    return manifest


def export_operator_memo(
    plan: Plan,
    sim: SimResult,
    constraints: Any,
    score_report: Any,
    out_path: Path,
    robustness: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Write a lightweight go/no-go memo for BVLOS inspection planning review.

    This is additive reporting only; core JSON contracts remain unchanged.
    """
    hard_pass = bool(getattr(constraints, "hard_pass", False))
    status = "GO" if hard_pass else "MODIFY / DO NOT FLY"
    waypoints = plan.waypoints or []
    inspection_points = max(0, len(waypoints) - 1)
    hard = sorted(list(_hard_constraints(constraints)), key=lambda result: result.min_margin)
    regulatory = _regulatory_metadata(cfg)
    weather = _weather_metadata(cfg)
    mission_metadata = _mission_metadata(cfg)
    fleet_metadata = _fleet_metadata(cfg)

    lines = [
        "# BVLOS Inspection Operator Memo",
        "",
        f"Status: {status}",
        "",
        "ORBITAL is preflight decision support and audit evidence. It is not a LAANC "
        "provider, autopilot, or regulatory approval system.",
        "",
        "## Mission Summary",
        "",
        f"- Mission: {plan.metadata.get('mission_id', 'aircraft_mission')}",
        f"- Inspection points: {inspection_points}",
        f"- Planned cruise speed: {_fmt_value(plan.metadata.get('cruise_speed_mps'), 'm/s')}",
        f"- Estimated flight time: {_fmt_value(_scalar(sim, 't_end_s'), 's')}",
        f"- Estimated energy used: {_fmt_value(_scalar(sim, 'energy_used_Wh'), 'Wh')}",
        f"- Final battery: {_fmt_value(_scalar(sim, 'final_battery_Wh'), 'Wh')}",
        f"- Objective score: {_fmt_value(getattr(score_report, 'total_score', None))}",
        "",
        "## Mission / Fleet Metadata",
        "",
        f"- Operator: {mission_metadata.get('operator') or 'not provided'}",
        f"- Aircraft ID: {mission_metadata.get('aircraft_id') or 'not provided'}",
        f"- Pilot: {mission_metadata.get('pilot') or 'not provided'}",
        f"- Organization: {mission_metadata.get('organization') or 'not provided'}",
        f"- Asset owner: {mission_metadata.get('asset_owner') or 'not provided'}",
        f"- Drone model: {fleet_metadata.get('drone_model') or 'not provided'}",
        f"- Battery pack ID: {fleet_metadata.get('battery_pack_id') or 'not provided'}",
        f"- Sensor payload: {fleet_metadata.get('sensor_payload') or 'not provided'}",
        f"- Inspection type: {fleet_metadata.get('inspection_type') or 'not provided'}",
        "",
        "## Weather",
        "",
        f"- Source: {weather.get('source') or 'not provided'}",
        f"- Timestamp: {weather.get('timestamp_utc') or 'not provided'}",
        f"- Wind speed: {_fmt_value(weather.get('wind_speed_mps'), 'm/s')}",
        f"- Wind gust: {_fmt_value(weather.get('wind_gust_mps'), 'm/s')}",
        f"- Visibility: {_fmt_value(weather.get('visibility_m'), 'm')}",
        f"- Precipitation: {_fmt_value(weather.get('precipitation_mm'), 'mm')}",
        f"- Fallback used: {_yes_no_unknown(weather.get('fallback_used'))}",
        "",
        "## Regulatory Metadata",
        "",
        f"- LAANC required: {_yes_no_unknown(regulatory.get('laanc_required'))}",
        "- Waiver / authorization required: "
        f"{_yes_no_unknown(regulatory.get('waiver_or_authorization_required'))}",
        f"- Airspace class: {regulatory.get('airspace_class') or 'unknown'}",
        f"- Visual observer required: {_yes_no_unknown(regulatory.get('visual_observer_required'))}",
        "- Ground-risk / population note: "
        f"{regulatory.get('ground_risk_population_note') or 'not provided'}",
        f"- Documentation-only notice: {regulatory.get('documentation_only_notice')}",
        "",
        "## Top Constraints",
        "",
    ]

    if hard:
        for result in hard[:5]:
            state = "PASS" if bool(result.is_satisfied) else "REVIEW"
            lines.append(
                f"- {state}: {_constraint_label(str(result.name))} "
                f"(margin {_fmt_value(float(result.min_margin))})"
            )
    else:
        lines.append("- No hard constraints were reported.")

    if robustness:
        lines.extend(
            [
                "",
                "## Robustness",
                "",
                f"- Cases: {robustness.get('cases', 'n/a')}",
                f"- Hard pass rate: {_fmt_value(robustness.get('hard_pass_rate'))}",
                "- Worst hard margin across cases: "
                f"{_fmt_value(robustness.get('worst_hard_margin_min'))}",
            ]
        )

    lines.extend(["", "## Recommended Next Actions", ""])
    lines.extend(f"- {action}" for action in _recommended_actions(constraints))

    memo = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(memo, encoding="utf-8")
    return memo


def print_flight_plan(plan: Plan, max_rows: int = 50) -> str:
    """
    Return a pretty text table for console printing.
    """
    rows = flight_plan_table(plan)
    rows = rows[:max_rows]

    # Pick common columns first
    preferred = ["seq", "id", "eta_s", "x_m", "y_m", "z_m", "lat_deg", "lon_deg", "alt_m"]
    columns = [c for c in preferred if any(c in r for r in rows)]
    # Add any other columns
    for r in rows:
        for k in r.keys():
            if k not in columns:
                columns.append(k)

    # Compute widths
    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v)

    widths = {c: max(len(c), *(len(_fmt(r.get(c, ""))) for r in rows)) for c in columns}

    lines = []
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    lines.append(header)
    lines.append(sep)

    for r in rows:
        lines.append(" | ".join(_fmt(r.get(c, "")).ljust(widths[c]) for c in columns))

    if len(flight_plan_table(plan)) > max_rows:
        lines.append(f"... ({len(flight_plan_table(plan)) - max_rows} more rows)")

    return "\n".join(lines)
