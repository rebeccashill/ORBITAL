from __future__ import annotations

from pathlib import Path

import pytest

from mission_framework.gis import GeoJSONError, load_geofence_zones, load_route_waypoints
from mission_framework.scenario_validation import collect_scenario_validation_issues

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_geojson_route_imports_powerline_waypoints() -> None:
    waypoints = load_route_waypoints(
        EXAMPLES / "geojson" / "bvlos_powerline_route.geojson",
        default_z_m=90.0,
        default_radius_m=70.0,
    )

    assert [waypoint["id"] for waypoint in waypoints] == [
        "TOWER_01",
        "TOWER_02",
        "TOWER_03",
        "TOWER_04",
        "TOWER_05",
        "TOWER_06",
    ]
    assert waypoints[0]["x_m"] == pytest.approx(750.0)
    assert waypoints[-1]["y_m"] == pytest.approx(120.0)
    assert {waypoint["radius_m"] for waypoint in waypoints} == {70.0}


def test_geojson_geofence_imports_polygon_zones() -> None:
    zones = load_geofence_zones(EXAMPLES / "geojson" / "bvlos_powerline_geofences.geojson")

    assert len(zones) == 1
    assert zones[0]["id"] == "SUBSTATION_NFZ_GEOJSON"
    assert zones[0]["polygon"] == [
        (2350.0, 450.0),
        (3050.0, 450.0),
        (3050.0, 850.0),
        (2350.0, 850.0),
    ]


def test_geojson_import_rejects_empty_or_malformed_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.geojson"
    empty.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    malformed = tmp_path / "malformed.geojson"
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(GeoJSONError, match="at least one feature"):
        load_route_waypoints(empty)
    with pytest.raises(GeoJSONError, match="malformed GeoJSON"):
        load_geofence_zones(malformed)


def test_scenario_validation_reports_bad_geojson_inputs(tmp_path: Path) -> None:
    bad_route = tmp_path / "bad_route.geojson"
    bad_route.write_text(
        '{"type": "FeatureCollection", "features": []}',
        encoding="utf-8",
    )
    bad_geofence = tmp_path / "bad_geofence.geojson"
    bad_geofence.write_text(
        '{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}',
        encoding="utf-8",
    )
    cfg = {
        "scenario": {"name": "Bad GIS", "type": "aircraft"},
        "initial_state": {
            "x_m": 0.0,
            "y_m": 0.0,
            "heading_rad": 0.0,
            "speed_mps": 10.0,
            "battery_Wh": 100.0,
        },
        "mission": {
            "fixed_order": True,
            "route_geojson_path": str(bad_route),
            "use_geojson_route": True,
        },
        "vehicle": {
            "dt_s": 1.0,
            "reach_radius_m": 10.0,
            "mass_kg": 1.0,
            "cruise_speed_mps": 10.0,
            "min_speed_mps": 5.0,
            "max_speed_mps": 15.0,
            "battery_capacity_Wh": 100.0,
        },
        "geofence": {
            "geojson_path": str(bad_geofence),
            "use_geojson": True,
        },
        "constraints": {"enforce_geofence": True},
        "objective": {
            "type": "weighted_sum",
            "terms": [{"name": "time", "weight": 1.0, "mode": "minimize"}],
        },
        "planner": {"iterations": 1, "restarts": 1},
        "robustness": {"cases": 0},
        "output": {"save_history": False},
    }

    paths = {issue.path for issue in collect_scenario_validation_issues(cfg)}
    assert "mission.route_geojson_path" in paths
    assert "geofence.geojson_path" in paths
