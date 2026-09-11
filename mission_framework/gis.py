"""GeoJSON import helpers for aircraft route and geofence inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


class GeoJSONError(ValueError):
    """Raised when a GeoJSON input cannot be parsed into ORBITAL geometry."""


def resolve_config_path(path_value: str, cfg: Mapping[str, Any]) -> Path:
    """Resolve a scenario path using scenario directory first, then cwd."""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate

    scenario_dir = cfg.get("_scenario_dir")
    if isinstance(scenario_dir, str) and scenario_dir.strip():
        resolved = Path(scenario_dir) / candidate
        if resolved.exists():
            return resolved

    return candidate


def _load_geojson(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise GeoJSONError(f"cannot read GeoJSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GeoJSONError(f"malformed GeoJSON file: {path}") from exc

    if not isinstance(payload, Mapping):
        raise GeoJSONError("GeoJSON root must be an object")
    return payload


def _features(payload: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    gtype = str(payload.get("type", "")).strip()
    if gtype == "FeatureCollection":
        raw_features = payload.get("features")
        if not isinstance(raw_features, list) or not raw_features:
            raise GeoJSONError("FeatureCollection must contain at least one feature")
        features = []
        for idx, feature in enumerate(raw_features):
            if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
                raise GeoJSONError(f"features[{idx}] must be a GeoJSON Feature")
            features.append(feature)
        return features

    if gtype == "Feature":
        return [payload]

    if gtype in {"LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
        return [{"type": "Feature", "properties": {}, "geometry": payload}]

    raise GeoJSONError(f"unsupported GeoJSON type '{gtype}'")


def _geometry(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    geometry = feature.get("geometry")
    if not isinstance(geometry, Mapping):
        raise GeoJSONError("Feature geometry must be an object")
    return geometry


def _properties(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    properties = feature.get("properties")
    return properties if isinstance(properties, Mapping) else {}


def _number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GeoJSONError(f"{label} must be a finite number") from exc
    if number != number or number in {float("inf"), float("-inf")}:
        raise GeoJSONError(f"{label} must be a finite number")
    return number


def _position(raw: Any, label: str) -> Tuple[float, float, Optional[float]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) < 2:
        raise GeoJSONError(f"{label} must be a coordinate position [x_m, y_m, ...]")
    x = _number(raw[0], f"{label}[0]")
    y = _number(raw[1], f"{label}[1]")
    z = _number(raw[2], f"{label}[2]") if len(raw) >= 3 else None
    return x, y, z


def _positions(raw: Any, label: str) -> List[Tuple[float, float, Optional[float]]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise GeoJSONError(f"{label} must contain at least one position")
    return [_position(item, f"{label}[{idx}]") for idx, item in enumerate(raw)]


def _outer_ring(raw: Any, label: str) -> List[Tuple[float, float]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise GeoJSONError(f"{label} must contain at least one linear ring")
    ring = _positions(raw[0], f"{label}[0]")
    if len(ring) < 4:
        raise GeoJSONError(f"{label}[0] must contain at least 4 positions")
    first = ring[0]
    last = ring[-1]
    if first[0] != last[0] or first[1] != last[1]:
        raise GeoJSONError(f"{label}[0] must be closed")
    polygon = [(float(x), float(y)) for x, y, _z in ring[:-1]]
    if len(polygon) < 3:
        raise GeoJSONError(f"{label}[0] must contain at least 3 unique coordinate pairs")
    return polygon


def _line_geometries(geometry: Mapping[str, Any]) -> Iterable[Any]:
    gtype = str(geometry.get("type", "")).strip()
    coords = geometry.get("coordinates")
    if gtype == "LineString":
        yield coords
    elif gtype == "MultiLineString":
        if not isinstance(coords, Sequence) or isinstance(coords, (str, bytes)) or not coords:
            raise GeoJSONError("MultiLineString must contain at least one line")
        yield from coords
    else:
        raise GeoJSONError(f"route GeoJSON must use LineString or MultiLineString, got '{gtype}'")


def _polygon_geometries(geometry: Mapping[str, Any]) -> Iterable[Any]:
    gtype = str(geometry.get("type", "")).strip()
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        yield coords
    elif gtype == "MultiPolygon":
        if not isinstance(coords, Sequence) or isinstance(coords, (str, bytes)) or not coords:
            raise GeoJSONError("MultiPolygon must contain at least one polygon")
        yield from coords
    else:
        raise GeoJSONError(f"geofence GeoJSON must use Polygon or MultiPolygon, got '{gtype}'")


def load_route_waypoints(
    path: Path,
    *,
    default_z_m: float = 0.0,
    default_radius_m: float = 10.0,
) -> List[Dict[str, Any]]:
    """Import route/asset LineString coordinates as aircraft waypoints."""
    payload = _load_geojson(path)
    waypoints: List[Dict[str, Any]] = []
    global_idx = 1

    for feature_idx, feature in enumerate(_features(payload), start=1):
        props = _properties(feature)
        geometry = _geometry(feature)
        prefix = str(
            props.get("waypoint_prefix")
            or props.get("id")
            or props.get("name")
            or f"GEOJSON_{feature_idx}"
        ).strip()
        waypoint_ids = props.get("waypoint_ids")
        radius_m = float(props.get("radius_m", default_radius_m))
        z_m = float(props.get("z_m", default_z_m))

        for line in _line_geometries(geometry):
            positions = _positions(line, "route.coordinates")
            if len(positions) < 2:
                raise GeoJSONError("route LineString must contain at least 2 positions")
            for point_idx, (x, y, z) in enumerate(positions, start=1):
                if isinstance(waypoint_ids, list) and len(waypoint_ids) >= point_idx:
                    waypoint_id = str(waypoint_ids[point_idx - 1])
                else:
                    waypoint_id = f"{prefix}_{global_idx:02d}"
                waypoints.append(
                    {
                        "id": waypoint_id,
                        "x_m": float(x),
                        "y_m": float(y),
                        "z_m": float(z if z is not None else z_m),
                        "radius_m": radius_m,
                    }
                )
                global_idx += 1

    if not waypoints:
        raise GeoJSONError("route GeoJSON did not contain any waypoints")
    return waypoints


def load_geofence_zones(path: Path) -> List[Dict[str, Any]]:
    """Import Polygon/MultiPolygon GeoJSON features as no-fly-zone polygons."""
    payload = _load_geojson(path)
    zones: List[Dict[str, Any]] = []

    for feature_idx, feature in enumerate(_features(payload), start=1):
        props = _properties(feature)
        geometry = _geometry(feature)
        base_id = str(props.get("id") or props.get("name") or f"GEOJSON_NFZ_{feature_idx}").strip()
        for polygon_idx, polygon_coords in enumerate(_polygon_geometries(geometry), start=1):
            zone_id = base_id if polygon_idx == 1 else f"{base_id}_{polygon_idx}"
            zones.append(
                {
                    "id": zone_id,
                    "polygon": _outer_ring(polygon_coords, "geofence.coordinates"),
                }
            )

    if not zones:
        raise GeoJSONError("geofence GeoJSON did not contain any polygons")
    return zones
