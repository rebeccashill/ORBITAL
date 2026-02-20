# mission_framework/aircraft/constraints.py
from __future__ import annotations

from typing import List

from mission_framework.core.constraints import (
    Constraint,
    FunctionalConstraint,
    Severity,
    margin_nonnegative,
    margin_leq,
)


def battery_nonnegative() -> Constraint:
    return FunctionalConstraint(
        "battery_nonnegative",
        fn=lambda sim: margin_nonnegative(sim.resource("battery_Wh")),
        severity=Severity.HARD,
    )


def no_fly_zone_avoidance() -> Constraint:
    # nfz_inside is 1.0 if inside any zone; require <= 0
    return FunctionalConstraint(
        "geofence_no_fly",
        fn=lambda sim: margin_leq(sim.resource("nfz_inside"), 0.0),
        severity=Severity.HARD,
    )


def complete_all_waypoints() -> Constraint:
    # require completed == total
    return FunctionalConstraint(
        "complete_all_waypoints",
        fn=lambda sim: margin_nonnegative(
            sim.scalar("waypoints_completed") - sim.scalar("waypoints_total")
        ),
        severity=Severity.HARD,
    )


def default_aircraft_constraints(enforce_geofence: bool = True) -> List[Constraint]:
    cs = [battery_nonnegative(), complete_all_waypoints()]
    if enforce_geofence:
        cs.append(no_fly_zone_avoidance())
    return cs
