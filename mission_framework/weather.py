"""Weather provider integration for aircraft mission planning.

The weather layer is deliberately small: it normalizes provider data into a
single snapshot, applies that snapshot to the existing aircraft wind config,
and keeps an offline fallback path for reproducible demos and tests.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class WeatherSnapshot:
    """Normalized weather observation/forecast fields used by ORBITAL."""

    provider: str
    source: str
    timestamp_utc: str
    location_name: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    forecast_window_start_utc: Optional[str]
    forecast_window_hours: Optional[float]
    wind_speed_mps: Optional[float]
    wind_direction_deg: Optional[float]
    wind_gust_mps: Optional[float]
    visibility_m: Optional[float]
    precipitation_mm: Optional[float]
    temperature_C: Optional[float]
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    live_fetch_enabled: bool = False

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "timestamp_utc": self.timestamp_utc,
            "location_name": self.location_name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "forecast_window_start_utc": self.forecast_window_start_utc,
            "forecast_window_hours": self.forecast_window_hours,
            "wind_speed_mps": self.wind_speed_mps,
            "wind_direction_deg": self.wind_direction_deg,
            "wind_gust_mps": self.wind_gust_mps,
            "visibility_m": self.visibility_m,
            "precipitation_mm": self.precipitation_mm,
            "temperature_C": self.temperature_C,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "live_fetch_enabled": self.live_fetch_enabled,
        }


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _location(
    weather_cfg: Mapping[str, Any],
) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    location = _mapping(weather_cfg.get("location"))
    return (
        str(location.get("name")).strip() if location.get("name") is not None else None,
        _as_float(location.get("latitude_deg")),
        _as_float(location.get("longitude_deg")),
    )


def _forecast_window(
    weather_cfg: Mapping[str, Any],
) -> Tuple[Optional[str], Optional[float]]:
    window = _mapping(weather_cfg.get("forecast_window"))
    start = window.get("start_utc")
    return (
        str(start).strip() if start is not None else None,
        _as_float(window.get("hours")),
    )


def _offline_snapshot(
    weather_cfg: Mapping[str, Any],
    *,
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
) -> WeatherSnapshot:
    offline = _mapping(weather_cfg.get("offline"))
    location_name, lat, lon = _location(weather_cfg)
    start_utc, hours = _forecast_window(weather_cfg)
    timestamp = (
        offline.get("timestamp_utc") or weather_cfg.get("timestamp_utc") or start_utc or _now_utc()
    )
    return WeatherSnapshot(
        provider=str(weather_cfg.get("provider", "offline")).strip().lower() or "offline",
        source=str(offline.get("source", "offline_sample")),
        timestamp_utc=str(timestamp),
        location_name=location_name,
        latitude_deg=lat,
        longitude_deg=lon,
        forecast_window_start_utc=start_utc,
        forecast_window_hours=hours,
        wind_speed_mps=_as_float(offline.get("wind_speed_mps")),
        wind_direction_deg=_as_float(offline.get("wind_direction_deg")),
        wind_gust_mps=_as_float(offline.get("wind_gust_mps")),
        visibility_m=_as_float(offline.get("visibility_m")),
        precipitation_mm=_as_float(offline.get("precipitation_mm")),
        temperature_C=_as_float(offline.get("temperature_C")),
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        live_fetch_enabled=False,
    )


def _open_meteo_snapshot(weather_cfg: Mapping[str, Any]) -> WeatherSnapshot:
    location_name, lat, lon = _location(weather_cfg)
    if lat is None or lon is None:
        raise ValueError("Open-Meteo weather requires location.latitude_deg and longitude_deg")

    timeout_s = float(weather_cfg.get("timeout_s", 6.0))
    params = {
        "latitude": f"{lat:.7f}",
        "longitude": f"{lon:.7f}",
        "current": ",".join(
            [
                "temperature_2m",
                "precipitation",
                "visibility",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ]
        ),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    url = f"{OPEN_METEO_ENDPOINT}?{urlencode(params)}"
    with urlopen(url, timeout=timeout_s) as response:  # nosec B310 - user-configured public API.
        payload = json.loads(response.read().decode("utf-8"))

    current = _mapping(payload.get("current"))
    start_utc, hours = _forecast_window(weather_cfg)
    timestamp = current.get("time") or weather_cfg.get("timestamp_utc") or _now_utc()
    timestamp_utc = str(timestamp)
    if timestamp_utc and not timestamp_utc.endswith("Z"):
        timestamp_utc = f"{timestamp_utc}Z"

    return WeatherSnapshot(
        provider="open_meteo",
        source="Open-Meteo Forecast API",
        timestamp_utc=timestamp_utc,
        location_name=location_name,
        latitude_deg=lat,
        longitude_deg=lon,
        forecast_window_start_utc=start_utc,
        forecast_window_hours=hours,
        wind_speed_mps=_as_float(current.get("wind_speed_10m")),
        wind_direction_deg=_as_float(current.get("wind_direction_10m")),
        wind_gust_mps=_as_float(current.get("wind_gusts_10m")),
        visibility_m=_as_float(current.get("visibility")),
        precipitation_mm=_as_float(current.get("precipitation")),
        temperature_C=_as_float(current.get("temperature_2m")),
        fallback_used=False,
        fallback_reason=None,
        live_fetch_enabled=True,
    )


def resolve_weather_snapshot(cfg: Mapping[str, Any]) -> Optional[WeatherSnapshot]:
    """Resolve scenario weather into a normalized snapshot."""
    weather_cfg = _mapping(cfg.get("weather"))
    if not weather_cfg or not bool(weather_cfg.get("enabled", True)):
        return None

    provider = str(weather_cfg.get("provider", "offline")).strip().lower()
    use_live = bool(weather_cfg.get("use_live", False))
    fallback_enabled = bool(weather_cfg.get("fallback_enabled", True))

    if provider in {"offline", "mock", "sample"}:
        return _offline_snapshot(weather_cfg)

    if provider in {"open_meteo", "open-meteo", "openmeteo"}:
        if use_live:
            try:
                return _open_meteo_snapshot(weather_cfg)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                if not fallback_enabled:
                    raise RuntimeError(f"Open-Meteo weather fetch failed: {exc}") from exc
                return _offline_snapshot(
                    weather_cfg,
                    fallback_used=True,
                    fallback_reason=f"Open-Meteo fetch failed: {exc}",
                )
        return _offline_snapshot(
            weather_cfg,
            fallback_used=True,
            fallback_reason="weather.use_live is false; using offline sample",
        )

    raise ValueError(f"Unknown weather.provider '{provider}'")


def wind_components_from_speed_direction(
    speed_mps: Optional[float],
    direction_deg: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Convert meteorological wind direction into ENU vector components."""
    if speed_mps is None or direction_deg is None:
        return None, None
    direction_rad = math.radians(float(direction_deg))
    east = -float(speed_mps) * math.sin(direction_rad)
    north = -float(speed_mps) * math.cos(direction_rad)
    return east, north


def apply_weather_to_config(cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve weather, attach metadata, and map it into aircraft wind config."""
    snapshot = resolve_weather_snapshot(cfg)
    if snapshot is None:
        return None

    weather_cfg = cfg.setdefault("weather", {})
    weather_cfg["resolved"] = snapshot.to_jsonable()

    if not bool(weather_cfg.get("apply_to_wind", True)):
        weather_cfg["applied_to_wind"] = False
        return snapshot.to_jsonable()

    east, north = wind_components_from_speed_direction(
        snapshot.wind_speed_mps,
        snapshot.wind_direction_deg,
    )
    if east is None or north is None:
        weather_cfg["applied_to_wind"] = False
        weather_cfg["wind_application_note"] = "missing wind speed or direction"
        return snapshot.to_jsonable()

    wind_cfg = cfg.setdefault("wind", {})
    wtype = str(wind_cfg.get("type", "sinusoidal")).strip().lower()
    if wtype in {"uniform", "constant"}:
        wind_cfg["w_east_mps"] = east
        wind_cfg["w_north_mps"] = north
        wind_cfg.setdefault("w_up_mps", 0.0)
    else:
        wind_cfg["type"] = "sinusoidal" if wtype in {"", "none", "zero", "no_wind"} else wtype
        wind_cfg["mean_east_mps"] = east
        wind_cfg["mean_north_mps"] = north
        wind_cfg.setdefault("mean_up_mps", 0.0)
        gust_delta = max(
            0.0, float(snapshot.wind_gust_mps or 0.0) - float(snapshot.wind_speed_mps or 0.0)
        )
        gust_east, gust_north = wind_components_from_speed_direction(
            gust_delta,
            snapshot.wind_direction_deg,
        )
        wind_cfg["amp_east_mps"] = gust_east or 0.0
        wind_cfg["amp_north_mps"] = gust_north or 0.0
        wind_cfg.setdefault("amp_up_mps", 0.0)
        wind_cfg.setdefault("period_s", 600.0)

    limits = _mapping(weather_cfg.get("operational_limits"))
    if "max_safe_wind_mps" in limits:
        wind_cfg["max_safe_wind_mps"] = float(limits["max_safe_wind_mps"])
    if "warning_margin_mps" in limits:
        wind_cfg["warning_margin_mps"] = float(limits["warning_margin_mps"])

    wind_cfg["weather_source"] = snapshot.source
    wind_cfg["weather_timestamp_utc"] = snapshot.timestamp_utc
    weather_cfg["applied_to_wind"] = True
    return snapshot.to_jsonable()
