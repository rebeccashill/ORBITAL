"""YAML scenario validation for ORBITAL.

Chosen approach: lightweight dataclass/manual validation.

That keeps validation close to the existing YAML contract without adding a
runtime dependency such as Pydantic or jsonschema. The public API reports all
detected issues at once so users can fix a scenario file in one pass.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable scenario validation problem."""

    path: str
    message: str
    hint: Optional[str] = None

    def __str__(self) -> str:
        if self.hint:
            return f"{self.path}: {self.message} Hint: {self.hint}"
        return f"{self.path}: {self.message}"


class ScenarioValidationError(ValueError):
    """Raised when a scenario YAML config does not satisfy the supported schema."""

    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = tuple(issues)
        lines = [f"Scenario validation failed with {len(self.issues)} issue(s):"]
        lines.extend(f"- {issue}" for issue in self.issues)
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class ScenarioSchema:
    """Readable description of the required YAML surface for a domain."""

    scenario_type: str
    required_sections: tuple[str, ...]
    required_fields: dict[str, tuple[str, ...]]


SHARED_SCENARIO_FIELDS = ("scenario.name", "scenario.type", "planner", "output", "robustness")

AIRCRAFT_SCHEMA = ScenarioSchema(
    scenario_type="aircraft",
    required_sections=(
        "scenario",
        "initial_state",
        "mission",
        "vehicle",
        "constraints",
        "objective",
        "planner",
        "robustness",
        "output",
    ),
    required_fields={
        "scenario": ("name", "type"),
        "mission.waypoints[]": ("id", "x_m", "y_m"),
        "vehicle": (
            "dt_s",
            "reach_radius_m",
            "mass_kg",
            "cruise_speed_mps",
            "min_speed_mps",
            "max_speed_mps",
            "battery_capacity_Wh",
        ),
    },
)

SPACECRAFT_SCHEMA = ScenarioSchema(
    scenario_type="spacecraft",
    required_sections=(
        "scenario",
        "orbit",
        "mission",
        "ground_stations",
        "spacecraft",
        "constraints",
        "objective",
        "planner",
        "robustness",
        "output",
    ),
    required_fields={
        "scenario": ("name", "type"),
        "orbit": ("altitude_km", "inclination_deg", "epoch_utc", "duration_days", "time_step_s"),
        "mission.targets[]": ("id", "lat_deg", "lon_deg", "value", "time_windows"),
        "ground_stations[]": ("id", "lat_deg", "lon_deg", "min_elevation_deg"),
        "spacecraft": (
            "battery_capacity_Wh",
            "initial_battery_Wh",
            "charge_rate_W",
            "base_load_W",
            "payload_power_W",
            "downlink_power_W",
            "max_slew_rate_deg_per_s",
            "min_cooldown_s",
            "max_ops_per_orbit",
            "data_storage_capacity_Gb",
            "data_rate_downlink_Mbps",
            "data_rate_observation_Mbps",
        ),
    },
)


def validate_scenario_file(path: str | Path, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Load and validate a YAML scenario file, returning the parsed config."""
    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    return validate_scenario_config(cfg, expected_type=expected_type)


def validate_scenario_config(
    cfg: Any,
    expected_type: Optional[str] = None,
) -> dict[str, Any]:
    """Validate a parsed YAML scenario config and return it on success."""
    issues = collect_scenario_validation_issues(cfg, expected_type=expected_type)
    if issues:
        raise ScenarioValidationError(issues)
    return dict(cfg)


def collect_scenario_validation_issues(
    cfg: Any,
    expected_type: Optional[str] = None,
) -> list[ValidationIssue]:
    """Return all validation issues without raising."""
    issues: list[ValidationIssue] = []

    if not isinstance(cfg, Mapping):
        return [
            ValidationIssue(
                "root",
                "must be a YAML mapping/object",
                "Start the file with top-level sections such as scenario, mission, and planner.",
            )
        ]

    scenario = _require_mapping(cfg, "scenario", issues)
    scenario_type = None
    if scenario is not None:
        _require_nonempty_string(scenario, "scenario.name", issues)
        scenario_type = _require_nonempty_string(scenario, "scenario.type", issues)
        if scenario_type is not None:
            scenario_type = scenario_type.strip().lower()
            if scenario_type not in {"aircraft", "spacecraft"}:
                issues.append(
                    ValidationIssue(
                        "scenario.type",
                        f"unknown scenario type '{scenario_type}'",
                        "Use 'aircraft' or 'spacecraft'.",
                    )
                )
            elif expected_type is not None and scenario_type != expected_type:
                issues.append(
                    ValidationIssue(
                        "scenario.type",
                        f"expected '{expected_type}', got '{scenario_type}'",
                    )
                )

    _validate_shared_sections(cfg, issues)

    if scenario_type == "aircraft":
        _validate_required_sections(cfg, AIRCRAFT_SCHEMA, issues)
        _validate_aircraft(cfg, issues)
    elif scenario_type == "spacecraft":
        _validate_required_sections(cfg, SPACECRAFT_SCHEMA, issues)
        _validate_spacecraft(cfg, issues)

    return _dedupe_issues(issues)


def _validate_shared_sections(cfg: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    planner = _require_mapping(cfg, "planner", issues)
    output = _require_mapping(cfg, "output", issues)
    robustness = _require_mapping(cfg, "robustness", issues)
    objective = _optional_mapping(cfg, "objective", issues)

    if planner is not None:
        _number(planner, "planner.iterations", issues, required=True, min_value=1, integer=True)
        _number(planner, "planner.restarts", issues, required=True, min_value=1, integer=True)
        _number(planner, "planner.penalty_weight", issues, min_value=0.0)
        _number(planner, "planner.hard_infeasible_penalty", issues, min_value=0.0)
        _number(planner, "planner.seed", issues, integer=True)
        _number(planner, "planner.history_stride", issues, min_value=1, integer=True)
        _number(planner, "planner.stop_if_feasible_for", issues, min_value=0, integer=True)

        mutation = _optional_mapping(planner, "planner.mutation", issues)
        if mutation is not None:
            _number(mutation, "planner.mutation.cont_sigma", issues, min_value=0.0)
            _number(mutation, "planner.mutation.int_step", issues, min_value=0, integer=True)
            _number(mutation, "planner.mutation.p_flip", issues, min_value=0.0, max_value=1.0)
            _number(
                mutation,
                "planner.mutation.p_perm_swap",
                issues,
                min_value=0.0,
                max_value=1.0,
            )
            _number(mutation, "planner.mutation.perm_swaps", issues, min_value=0, integer=True)

    if output is not None:
        for key, value in output.items():
            if not isinstance(value, bool):
                issues.append(
                    ValidationIssue(
                        f"output.{key}",
                        "must be a boolean",
                        "Use true or false.",
                    )
                )

    if robustness is not None:
        _number(robustness, "robustness.cases", issues, required=True, min_value=0, integer=True)
        _number(robustness, "robustness.battery_variation_pct", issues, min_value=0.0)
        _number(robustness, "robustness.slew_rate_variation_pct", issues, min_value=0.0)
        _number(robustness, "robustness.contact_timing_jitter_s", issues, min_value=0.0)
        _validate_numeric_range(robustness, "robustness.wind_scale_range", issues, min_value=0.0)
        _validate_percentiles(robustness, "robustness.report_percentiles", issues)
        aggregation = robustness.get("aggregation")
        if aggregation is not None and str(aggregation).strip().lower() not in {
            "mean",
            "worst",
            "cvar",
        }:
            issues.append(
                ValidationIssue(
                    "robustness.aggregation",
                    "must be one of: mean, worst, cvar",
                )
            )
        _number(robustness, "robustness.cvar_alpha", issues, min_value=0.0, max_value=1.0)

    if objective is not None:
        if objective.get("type") is not None and str(objective["type"]).strip().lower() != "weighted_sum":
            issues.append(
                ValidationIssue(
                    "objective.type",
                    "must be 'weighted_sum'",
                    "The current planner combines objective terms as a weighted sum.",
                )
            )
        terms = _require_sequence(objective, "objective.terms", issues)
        if terms is not None:
            for idx, term in enumerate(terms):
                path = f"objective.terms[{idx}]"
                if not isinstance(term, Mapping):
                    issues.append(ValidationIssue(path, "must be a mapping/object"))
                    continue
                _require_nonempty_string(term, f"{path}.name", issues)
                _number(term, f"{path}.weight", issues, required=True, min_value=0.0)
                mode = _require_nonempty_string(term, f"{path}.mode", issues)
                if mode is not None and mode.strip().lower() not in {"minimize", "maximize"}:
                    issues.append(
                        ValidationIssue(
                            f"{path}.mode",
                            "must be 'minimize' or 'maximize'",
                        )
                    )


def _validate_required_sections(
    cfg: Mapping[str, Any],
    schema: ScenarioSchema,
    issues: list[ValidationIssue],
) -> None:
    for section in schema.required_sections:
        if section == "ground_stations":
            _require_sequence(cfg, section, issues)
        else:
            _require_mapping(cfg, section, issues)


def _validate_aircraft(cfg: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    initial_state = _optional_mapping(cfg, "initial_state", issues)
    mission = _optional_mapping(cfg, "mission", issues)
    vehicle = _optional_mapping(cfg, "vehicle", issues)
    wind = _optional_mapping(cfg, "wind", issues)
    geofence = _optional_mapping(cfg, "geofence", issues)
    constraints = _optional_mapping(cfg, "constraints", issues)
    objective = _optional_mapping(cfg, "objective", issues)
    simulation = _optional_mapping(cfg, "simulation", issues)

    if initial_state is not None:
        for key in ("x_m", "y_m", "heading_rad", "speed_mps", "battery_Wh"):
            _number(initial_state, f"initial_state.{key}", issues, required=True)
        _number(initial_state, "initial_state.z_m", issues)
        _number(initial_state, "initial_state.speed_mps", issues, min_value=0.0)
        _number(initial_state, "initial_state.battery_Wh", issues, min_value=0.0)

    if mission is not None:
        waypoints = _require_sequence(mission, "mission.waypoints", issues)
        if waypoints is not None:
            if not waypoints:
                issues.append(ValidationIssue("mission.waypoints", "must contain at least one waypoint"))
            _validate_unique_ids(waypoints, "mission.waypoints", issues)
            for idx, waypoint in enumerate(waypoints):
                path = f"mission.waypoints[{idx}]"
                if not isinstance(waypoint, Mapping):
                    issues.append(ValidationIssue(path, "must be a mapping/object"))
                    continue
                _require_nonempty_string(waypoint, f"{path}.id", issues)
                _number(waypoint, f"{path}.x_m", issues, required=True)
                _number(waypoint, f"{path}.y_m", issues, required=True)
                _number(waypoint, f"{path}.z_m", issues)
                _number(waypoint, f"{path}.radius_m", issues, min_value=0.0)

    if vehicle is not None:
        for key in (
            "dt_s",
            "reach_radius_m",
            "mass_kg",
            "cruise_speed_mps",
            "min_speed_mps",
            "max_speed_mps",
            "battery_capacity_Wh",
        ):
            _number(vehicle, f"vehicle.{key}", issues, required=True, min_value=0.0)
        for key in (
            "max_turn_rate_radps",
            "yaw_rate_max_radps",
            "energy_rate_cruise_W",
            "energy_rate_turn_W",
            "p_idle_W",
            "k_v_W_per_m2s2",
            "k_climb_W_per_mps",
            "k_turn_W_per_radps",
            "bank_max_deg",
            "climb_rate_max_mps",
            "descent_rate_max_mps",
        ):
            _number(vehicle, f"vehicle.{key}", issues, min_value=0.0)
        _number(vehicle, "vehicle.z_min_m", issues)
        _number(vehicle, "vehicle.z_max_m", issues)
        min_speed = _coerce_number(vehicle.get("min_speed_mps"))
        cruise_speed = _coerce_number(vehicle.get("cruise_speed_mps"))
        max_speed = _coerce_number(vehicle.get("max_speed_mps"))
        if min_speed is not None and max_speed is not None and min_speed > max_speed:
            issues.append(
                ValidationIssue(
                    "vehicle.min_speed_mps",
                    "must be less than or equal to vehicle.max_speed_mps",
                )
            )
        if (
            min_speed is not None
            and cruise_speed is not None
            and max_speed is not None
            and not min_speed <= cruise_speed <= max_speed
        ):
            issues.append(
                ValidationIssue(
                    "vehicle.cruise_speed_mps",
                    "must fall between vehicle.min_speed_mps and vehicle.max_speed_mps",
                )
            )

    if wind is not None:
        wind_type = str(wind.get("type", "sinusoidal")).strip().lower()
        valid_wind_types = {
            "none",
            "no_wind",
            "zero",
            "uniform",
            "constant",
            "vortex",
            "swirl",
            "sinusoidal",
        }
        if wind_type not in valid_wind_types:
            issues.append(
                ValidationIssue(
                    "wind.type",
                    f"unknown wind type '{wind_type}'",
                    f"Use one of: {', '.join(sorted(valid_wind_types))}.",
                )
            )
        for key in (
            "base_speed_mps",
            "direction_rad",
            "gust_amplitude_mps",
            "gust_frequency_hz",
            "w_east_mps",
            "w_north_mps",
            "w_up_mps",
            "mean_east_mps",
            "mean_north_mps",
            "mean_up_mps",
            "amp_east_mps",
            "amp_north_mps",
            "amp_up_mps",
            "center_x_m",
            "center_y_m",
            "swirl_strength",
            "core_radius_m",
            "vertical_shear",
            "period_s",
            "phase_s",
            "sigma_bias_mps",
            "sigma_gust_mps",
            "tau_gust_s",
        ):
            _number(wind, f"wind.{key}", issues)
        _number(wind, "wind.period_s", issues, min_value=0.0, exclusive_min=True)
        _number(wind, "wind.core_radius_m", issues, min_value=0.0, exclusive_min=True)
        _number(wind, "wind.tau_gust_s", issues, min_value=0.0, exclusive_min=True)
        if "stochastic" in wind and not isinstance(wind["stochastic"], bool):
            issues.append(ValidationIssue("wind.stochastic", "must be a boolean"))

    if geofence is not None:
        _number(geofence, "geofence.clearance_m", issues, min_value=0.0)
        zones = _optional_sequence(geofence, "geofence.no_fly_zones", issues)
        if zones is not None:
            _validate_unique_ids(zones, "geofence.no_fly_zones", issues)
            for idx, zone in enumerate(zones):
                path = f"geofence.no_fly_zones[{idx}]"
                if not isinstance(zone, Mapping):
                    issues.append(ValidationIssue(path, "must be a mapping/object"))
                    continue
                _require_nonempty_string(zone, f"{path}.id", issues)
                _validate_polygon(zone, f"{path}.polygon", issues)

    if constraints is not None:
        _validate_boolean_map(constraints, "constraints", issues)

    if objective is not None:
        _validate_objective_terms(
            objective,
            "objective.terms",
            {
                "total_time",
                "time",
                "t_end_s",
                "energy_used",
                "energy",
                "energy_used_wh",
            },
            issues,
        )

    if simulation is not None:
        for key in ("t_max_s", "stall_time_s", "stall_improve_m", "k_heading", "k_speed"):
            _number(simulation, f"simulation.{key}", issues, min_value=0.0)
        _number(simulation, "simulation.max_speed_step_mps", issues, min_value=0.0)


def _validate_spacecraft(cfg: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    orbit = _optional_mapping(cfg, "orbit", issues)
    mission = _optional_mapping(cfg, "mission", issues)
    ground_stations = _optional_sequence(cfg, "ground_stations", issues)
    spacecraft = _optional_mapping(cfg, "spacecraft", issues)
    constraints = _optional_mapping(cfg, "constraints", issues)
    objective = _optional_mapping(cfg, "objective", issues)
    downlink = _optional_mapping(cfg, "downlink", issues)
    power = _optional_mapping(cfg, "power", issues)
    ops = _optional_mapping(cfg, "ops", issues)

    if orbit is not None:
        _number(orbit, "orbit.altitude_km", issues, required=True, min_value=0.0, exclusive_min=True)
        _number(orbit, "orbit.inclination_deg", issues, required=True, min_value=0.0, max_value=180.0)
        _number(orbit, "orbit.raan_deg", issues)
        _number(orbit, "orbit.true_anomaly_deg", issues)
        _datetime(orbit, "orbit.epoch_utc", issues, required=True)
        _number(orbit, "orbit.duration_days", issues, required=True, min_value=0.0, exclusive_min=True)
        _number(orbit, "orbit.time_step_s", issues, required=True, min_value=0.0, exclusive_min=True)

    if mission is not None:
        targets = _require_sequence(mission, "mission.targets", issues)
        if targets is not None:
            if not targets:
                issues.append(ValidationIssue("mission.targets", "must contain at least one target"))
            _validate_unique_ids(targets, "mission.targets", issues)
            for idx, target in enumerate(targets):
                path = f"mission.targets[{idx}]"
                if not isinstance(target, Mapping):
                    issues.append(ValidationIssue(path, "must be a mapping/object"))
                    continue
                _require_nonempty_string(target, f"{path}.id", issues)
                _number(target, f"{path}.lat_deg", issues, required=True, min_value=-90.0, max_value=90.0)
                _number(target, f"{path}.lon_deg", issues, required=True, min_value=-180.0, max_value=180.0)
                _number(target, f"{path}.value", issues, required=True, min_value=0.0)
                _number(target, f"{path}.obs_duration_s", issues, min_value=0.0, exclusive_min=True)
                _number(target, f"{path}.cooldown_s", issues, min_value=0.0)
                _validate_time_windows(target, f"{path}.time_windows", issues, required=True)

    if ground_stations is not None:
        if not ground_stations:
            issues.append(ValidationIssue("ground_stations", "must contain at least one station"))
        _validate_unique_ids(ground_stations, "ground_stations", issues)
        for idx, station in enumerate(ground_stations):
            path = f"ground_stations[{idx}]"
            if not isinstance(station, Mapping):
                issues.append(ValidationIssue(path, "must be a mapping/object"))
                continue
            _require_nonempty_string(station, f"{path}.id", issues)
            _number(station, f"{path}.lat_deg", issues, required=True, min_value=-90.0, max_value=90.0)
            _number(station, f"{path}.lon_deg", issues, required=True, min_value=-180.0, max_value=180.0)
            _number(station, f"{path}.alt_km", issues)
            _number(
                station,
                f"{path}.min_elevation_deg",
                issues,
                required=True,
                min_value=0.0,
                max_value=90.0,
            )

    if spacecraft is not None:
        for key in (
            "battery_capacity_Wh",
            "initial_battery_Wh",
            "charge_rate_W",
            "base_load_W",
            "payload_power_W",
            "downlink_power_W",
            "max_slew_rate_deg_per_s",
            "min_cooldown_s",
            "max_ops_per_orbit",
            "data_storage_capacity_Gb",
            "data_rate_downlink_Mbps",
            "data_rate_observation_Mbps",
        ):
            _number(spacecraft, f"spacecraft.{key}", issues, required=True, min_value=0.0)
        _number(
            spacecraft,
            "spacecraft.max_slew_rate_deg_per_s",
            issues,
            min_value=0.0,
            exclusive_min=True,
        )
        _number(spacecraft, "spacecraft.max_ops_per_orbit", issues, min_value=1, integer=True)
        for key in (
            "battery_capacity_Wh",
            "data_storage_capacity_Gb",
            "data_rate_downlink_Mbps",
            "data_rate_observation_Mbps",
        ):
            _number(spacecraft, f"spacecraft.{key}", issues, min_value=0.0, exclusive_min=True)
        capacity = _coerce_number(spacecraft.get("battery_capacity_Wh"))
        initial = _coerce_number(spacecraft.get("initial_battery_Wh"))
        if capacity is not None and initial is not None and initial > capacity:
            issues.append(
                ValidationIssue(
                    "spacecraft.initial_battery_Wh",
                    "must be less than or equal to spacecraft.battery_capacity_Wh",
                )
            )

    if constraints is not None:
        _validate_boolean_map(constraints, "constraints", issues)

    if objective is not None:
        _validate_objective_terms(
            objective,
            "objective.terms",
            {
                "science_value_delivered",
                "value",
                "mission_value",
                "missed_downlink_penalty",
                "power_violation_penalty",
            },
            issues,
        )

    if downlink is not None:
        _number(downlink, "downlink.duration_s", issues, min_value=0.0, exclusive_min=True)
        _number(downlink, "downlink.max_windows_per_station", issues, min_value=1, integer=True)

    if power is not None:
        _number(power, "power.min_Wh", issues, min_value=0.0)

    if ops is not None:
        _number(ops, "ops.orbit_period_s", issues, min_value=0.0, exclusive_min=True)


def _require_mapping(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> Optional[Mapping[str, Any]]:
    value = _get_path(container, path)
    if value is None:
        issues.append(ValidationIssue(path, "required section is missing"))
        return None
    if not isinstance(value, Mapping):
        issues.append(ValidationIssue(path, "must be a mapping/object"))
        return None
    return value


def _optional_mapping(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> Optional[Mapping[str, Any]]:
    value = _get_path(container, path)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        issues.append(ValidationIssue(path, "must be a mapping/object"))
        return None
    return value


def _require_sequence(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> Optional[Sequence[Any]]:
    value = _get_path(container, path)
    if value is None:
        issues.append(ValidationIssue(path, "required list is missing"))
        return None
    if _is_non_string_sequence(value):
        return value
    issues.append(ValidationIssue(path, "must be a list"))
    return None


def _optional_sequence(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> Optional[Sequence[Any]]:
    value = _get_path(container, path)
    if value is None:
        return None
    if _is_non_string_sequence(value):
        return value
    issues.append(ValidationIssue(path, "must be a list"))
    return None


def _require_nonempty_string(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> Optional[str]:
    value = _get_path(container, path)
    if value is None:
        issues.append(ValidationIssue(path, "required field is missing"))
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(path, "must be a non-empty string"))
        return None
    return value


def _number(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
    *,
    required: bool = False,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    exclusive_min: bool = False,
    integer: bool = False,
) -> Optional[float]:
    value = _get_path(container, path)
    if value is None:
        if required:
            issues.append(ValidationIssue(path, "required numeric field is missing"))
        return None

    number = _coerce_number(value)
    if number is None:
        issues.append(ValidationIssue(path, "must be a finite number"))
        return None

    if integer and not float(number).is_integer():
        issues.append(ValidationIssue(path, "must be an integer"))

    if min_value is not None:
        violates_min = number <= min_value if exclusive_min else number < min_value
        if violates_min:
            op = "greater than" if exclusive_min else "greater than or equal to"
            issues.append(ValidationIssue(path, f"must be {op} {min_value:g}"))

    if max_value is not None and number > max_value:
        issues.append(ValidationIssue(path, f"must be less than or equal to {max_value:g}"))

    return number


def _datetime(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
    *,
    required: bool = False,
) -> Optional[datetime]:
    value = _get_path(container, path)
    if value is None:
        if required:
            issues.append(ValidationIssue(path, "required datetime field is missing"))
        return None
    parsed = _parse_datetime(value)
    if parsed is None:
        issues.append(
            ValidationIssue(
                path,
                "must be an ISO-8601 datetime string",
                "Example: 2026-01-01T00:00:00Z",
            )
        )
    return parsed


def _validate_time_windows(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
    *,
    required: bool = False,
) -> None:
    windows = _require_sequence(container, path, issues) if required else _optional_sequence(container, path, issues)
    if windows is None:
        return
    if not windows:
        issues.append(ValidationIssue(path, "must contain at least one time window"))
    for idx, window in enumerate(windows):
        item_path = f"{path}[{idx}]"
        if not isinstance(window, Mapping):
            issues.append(ValidationIssue(item_path, "must be a mapping/object"))
            continue
        start = _datetime(window, f"{item_path}.start_utc", issues, required=True)
        end = _datetime(window, f"{item_path}.end_utc", issues, required=True)
        if start is not None and end is not None and end <= start:
            issues.append(
                ValidationIssue(
                    f"{item_path}.end_utc",
                    "must be later than start_utc",
                )
            )


def _validate_polygon(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    polygon = _require_sequence(container, path, issues)
    if polygon is None:
        return
    if len(polygon) < 3:
        issues.append(ValidationIssue(path, "must contain at least 3 coordinate pairs"))
    for idx, point in enumerate(polygon):
        point_path = f"{path}[{idx}]"
        if not _is_non_string_sequence(point) or len(point) != 2:
            issues.append(ValidationIssue(point_path, "must be a coordinate pair [x_m, y_m]"))
            continue
        x, y = _coerce_number(point[0]), _coerce_number(point[1])
        if x is None or y is None:
            issues.append(ValidationIssue(point_path, "coordinates must be finite numbers"))


def _validate_boolean_map(
    mapping: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    for key, value in mapping.items():
        if not isinstance(value, bool):
            issues.append(
                ValidationIssue(
                    f"{path}.{key}",
                    "must be a boolean",
                    "Use true or false.",
                )
            )


def _validate_objective_terms(
    objective: Mapping[str, Any],
    path: str,
    allowed_names: set[str],
    issues: list[ValidationIssue],
) -> None:
    terms = _optional_sequence(objective, path, issues)
    if terms is None:
        return
    for idx, term in enumerate(terms):
        item_path = f"{path}[{idx}]"
        if not isinstance(term, Mapping):
            continue
        name = str(term.get("name", "")).strip().lower()
        if name and name not in allowed_names:
            issues.append(
                ValidationIssue(
                    f"{item_path}.name",
                    f"unknown objective term '{name}'",
                    f"Use one of: {', '.join(sorted(allowed_names))}.",
                )
            )


def _validate_unique_ids(
    items: Sequence[Any],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    seen: dict[str, int] = {}
    for idx, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        raw = item.get("id")
        if raw is None:
            continue
        identifier = str(raw)
        if identifier in seen:
            issues.append(
                ValidationIssue(
                    f"{path}[{idx}].id",
                    f"duplicates {path}[{seen[identifier]}].id",
                    "IDs must be unique within this list.",
                )
            )
        else:
            seen[identifier] = idx


def _validate_numeric_range(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
    *,
    min_value: Optional[float] = None,
) -> None:
    value = _get_path(container, path)
    if value is None:
        return
    if not _is_non_string_sequence(value) or len(value) != 2:
        issues.append(ValidationIssue(path, "must be a two-item numeric range [low, high]"))
        return
    low, high = _coerce_number(value[0]), _coerce_number(value[1])
    if low is None or high is None:
        issues.append(ValidationIssue(path, "range bounds must be finite numbers"))
        return
    if min_value is not None and (low < min_value or high < min_value):
        issues.append(ValidationIssue(path, f"range bounds must be greater than or equal to {min_value:g}"))
    if low > high:
        issues.append(ValidationIssue(path, "range low value must be less than or equal to high value"))


def _validate_percentiles(
    container: Mapping[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    value = _get_path(container, path)
    if value is None:
        return
    if not _is_non_string_sequence(value):
        issues.append(ValidationIssue(path, "must be a list of percentiles"))
        return
    for idx, item in enumerate(value):
        percentile = _coerce_number(item)
        if percentile is None:
            issues.append(ValidationIssue(f"{path}[{idx}]", "must be a finite number"))
        elif percentile < 0.0 or percentile > 100.0:
            issues.append(ValidationIssue(f"{path}[{idx}]", "must be between 0 and 100"))


def _get_path(container: Mapping[str, Any], path: str) -> Any:
    current: Any = container
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            break
        current = current[part]
    else:
        return current

    leaf = path.rsplit(".", 1)[-1]
    if isinstance(container, Mapping) and leaf in container:
        return container[leaf]
    return None


def _coerce_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _is_non_string_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _dedupe_issues(issues: Sequence[ValidationIssue]) -> list[ValidationIssue]:
    deduped: list[ValidationIssue] = []
    seen: set[tuple[str, str, Optional[str]]] = set()
    for issue in issues:
        key = (issue.path, issue.message, issue.hint)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped
