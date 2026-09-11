from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from mission_framework import weather as weather_module
from mission_framework.weather import (
    apply_weather_to_config,
    resolve_weather_snapshot,
    wind_components_from_speed_direction,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_offline_weather_maps_to_existing_wind_config() -> None:
    cfg = _load_yaml(EXAMPLES_DIR / "bvlos_powerline_inspection_demo.yaml")

    resolved = apply_weather_to_config(cfg)

    assert resolved is not None
    assert resolved["provider"] == "open_meteo"
    assert resolved["source"] == "offline Open-Meteo-shaped sample"
    assert resolved["fallback_used"] is True
    assert cfg["weather"]["applied_to_wind"] is True
    east, north = wind_components_from_speed_direction(4.5, 285.0)
    assert cfg["wind"]["mean_east_mps"] == pytest.approx(east)
    assert cfg["wind"]["mean_north_mps"] == pytest.approx(north)
    assert cfg["wind"]["weather_timestamp_utc"] == "2026-09-11T16:00:00Z"


def test_open_meteo_provider_parses_live_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "current": {
                        "time": "2026-09-11T17:00",
                        "temperature_2m": 21.2,
                        "precipitation": 0.1,
                        "visibility": 12000.0,
                        "wind_speed_10m": 6.2,
                        "wind_direction_10m": 250.0,
                        "wind_gusts_10m": 8.4,
                    }
                }
            ).encode("utf-8")

    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        assert "api.open-meteo.com" in url
        assert "wind_speed_unit=ms" in url
        assert timeout == pytest.approx(6.0)
        return FakeResponse()

    monkeypatch.setattr(weather_module, "urlopen", fake_urlopen)
    cfg = {
        "weather": {
            "enabled": True,
            "provider": "open_meteo",
            "use_live": True,
            "fallback_enabled": False,
            "timeout_s": 6.0,
            "location": {
                "name": "Test corridor",
                "latitude_deg": 37.4419,
                "longitude_deg": -122.1430,
            },
            "forecast_window": {
                "start_utc": "2026-09-11T17:00:00Z",
                "hours": 2.0,
            },
        }
    }

    snapshot = resolve_weather_snapshot(cfg)

    assert snapshot is not None
    assert snapshot.provider == "open_meteo"
    assert snapshot.source == "Open-Meteo Forecast API"
    assert snapshot.timestamp_utc == "2026-09-11T17:00Z"
    assert snapshot.wind_speed_mps == pytest.approx(6.2)
    assert snapshot.wind_direction_deg == pytest.approx(250.0)
    assert snapshot.wind_gust_mps == pytest.approx(8.4)
    assert snapshot.visibility_m == pytest.approx(12000.0)
    assert snapshot.precipitation_mm == pytest.approx(0.1)
    assert snapshot.temperature_C == pytest.approx(21.2)
    assert snapshot.live_fetch_enabled is True
    assert snapshot.fallback_used is False
