# ORBITAL/main.py

import numpy as np

from mission_framework.core.planner import Planner, PlannerConfig, Problem
from mission_framework.core.decision_variables import DecisionSpace, PermutationVar
from mission_framework.core.constraints import FunctionalConstraint, Severity
from mission_framework.core.objective import Objective, term_minimize_time


# -----------------------------
# Mission Definition
# -----------------------------

WAYPOINTS = np.array([
    [0.0, 0.0],
    [1000.0, 0.0],
    [1000.0, 1000.0],
    [0.0, 1000.0],
])

CRUISE_SPEED = 50.0  # m/s
MAX_TIME_S = 80.0    # hard constraint


# -----------------------------
# Build Plan From Decisions
# -----------------------------

def build_plan(decisions):
    return {
        "order": decisions["visit_order"]
    }


# -----------------------------
# Simulation Model
# -----------------------------

def simulate(plan, rng=None):
    order = plan["order"]
    pts = WAYPOINTS[order]

    total_dist = 0.0
    for i in range(len(pts) - 1):
        total_dist += float(np.linalg.norm(pts[i + 1] - pts[i]))

    mission_time = total_dist / CRUISE_SPEED

    return {
        "order": order,
        "total_dist_m": total_dist,
        "t_end_s": mission_time,
    }


# -----------------------------
# Main Execution
# -----------------------------

def main():

    # Decision space
    space = DecisionSpace([
        PermutationVar("visit_order", items=[0, 1, 2, 3]),
    ])

    # Constraints
    constraints = [
        FunctionalConstraint(
            name="max_time",
            severity=Severity.HARD,
            fn=lambda sim: MAX_TIME_S - sim["t_end_s"],  # must be >= 0
        )
    ]

    # Objective: minimize mission time
    objective = Objective([
        term_minimize_time()
    ])

    # Build problem
    problem = Problem(
        decision_space=space,
        build_plan=build_plan,
        simulate=simulate,
        constraints=constraints,
        objective=objective,
        robustness_cases=0,
    )

    # Solve
    planner = Planner(
        PlannerConfig(
            iterations=1000,
            restarts=5,
            seed=42,
        )
    )

    result = planner.solve(problem)

    # Output
    print("\n=== OPTIMIZED MISSION ===")
    print("Visit Order:", result.sim_result["order"])
    print("Total Distance (m):", result.sim_result["total_dist_m"])
    print("Mission Time (s):", result.sim_result["t_end_s"])
    print("Hard Constraints Pass:", result.constraints.hard_pass)
    print("Objective Cost:", result.objective.total_cost())
    print("Final Score:", result.score)


if __name__ == "__main__":
    main()
