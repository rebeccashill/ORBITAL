from __future__ import annotations
from typing import Any, Dict
import numpy as np

from mission_framework.core.decision_variables import DecisionSpace, BinaryVar, DecisionAssignment
from mission_framework.core.constraints import FunctionalConstraint, margin_nonnegative, Severity
from mission_framework.core.objective import Objective, term_maximize_value
from mission_framework.core.planner import Problem
from mission_framework.core.types import Event, EventType, Plan, Schedule, SimResult

def build_problem_from_config(cfg: Dict[str, Any]) -> Problem:
    # Minimal dummy spacecraft problem (schedules one optional observation)
    ds = DecisionSpace([BinaryVar("do_obs", shape=(1,))])

    def build_plan(a: DecisionAssignment) -> Plan:
        do_obs = int(np.array(a["do_obs"]).reshape(-1)[0])
        events = []
        if do_obs == 1:
            events.append(Event(0.0, 60.0, EventType.OBSERVATION, label="OBS_TGT1", target_id="TGT1"))
        sched = Schedule(events=events)
        return Plan(kind="spacecraft", schedule=sched)

    def simulate(plan: Plan, rng: np.random.Generator | None) -> SimResult:
        t = np.arange(0.0, 301.0, 30.0)
        # mission value depends on whether we scheduled the observation
        value = 10.0 if (plan.schedule and len(plan.schedule.events) > 0) else 0.0
        batt = np.full_like(t, 100.0)
        return SimResult(t=t, schedule=plan.schedule, scalars={"mission_value": value}, resources={"battery_Wh": batt})

    constraints = [
        FunctionalConstraint("battery_nonnegative", fn=lambda sim: margin_nonnegative(sim.resource("battery_Wh")), severity=Severity.HARD),
    ]
    objective = Objective([term_maximize_value()])

    return Problem(
        decision_space=ds,
        build_plan=build_plan,
        simulate=simulate,
        constraints=constraints,
        objective=objective,
        robustness_cases=0,
    )
