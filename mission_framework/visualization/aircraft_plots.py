"""
Aircraft mission plotting utilities.
Generates visualizations for flight paths, battery state, and mission performance.
"""

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt

from mission_framework.core.types import Plan, SimResult


def plot_aircraft_mission(
    plan: Plan, sim_result: SimResult, output_dir: Path, mission_name: str = "Aircraft Mission"
) -> Dict[str, Path]:
    """
    Generate plots for aircraft mission.

    Args:
        plan: Mission plan with waypoints
        sim_result: Simulation result with trajectory
        output_dir: Directory to save plots
        mission_name: Name for plot titles

    Returns:
        Dictionary mapping plot names to file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_files = {}

    # Extract trajectory data
    traj = sim_result.trajectory
    if traj is None or traj.t is None or traj.state is None:
        return plot_files

    t = traj.t
    state = traj.state

    # State order from metadata: [x_m, y_m, z_m, heading_rad, v_air_mps, battery_Wh]
    x = state[:, 0]
    y = state[:, 1]
    battery = state[:, 5] if state.shape[1] > 5 else None

    # Extract waypoints from plan
    waypoints = plan.waypoints if plan.waypoints else []

    # --- Plot 1: Flight Path (2D) ---
    fig1, ax1 = plt.subplots(figsize=(10, 8))

    # Plot trajectory
    ax1.plot(x, y, "b-", linewidth=2, alpha=0.7, label="Flight Path")
    ax1.plot(x[0], y[0], "go", markersize=12, label="Start", zorder=5)

    # Plot waypoints
    wp_x = [wp.get("x_m", 0.0) for wp in waypoints]
    wp_y = [wp.get("y_m", 0.0) for wp in waypoints]
    wp_ids = [wp.get("id", f"WP{i}") for i, wp in enumerate(waypoints)]

    # Skip START marker (already plotted)
    if len(wp_x) > 1:
        ax1.plot(wp_x[1:], wp_y[1:], "r^", markersize=10, label="Waypoints", zorder=5)

        # Annotate waypoints
        for i in range(1, len(wp_x)):
            ax1.annotate(
                wp_ids[i],
                (wp_x[i], wp_y[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
            )

    ax1.set_xlabel("X Position (m)", fontsize=12)
    ax1.set_ylabel("Y Position (m)", fontsize=12)
    ax1.set_title(f"{mission_name} - Flight Path", fontsize=14, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="best")
    ax1.axis("equal")

    path_file = output_dir / "flight_path.png"
    fig1.savefig(path_file, dpi=150, bbox_inches="tight")
    plt.close(fig1)
    plot_files["flight_path"] = path_file

    # --- Plot 2: Battery State Over Time ---
    if battery is not None:
        fig2, ax2 = plt.subplots(figsize=(10, 6))

        ax2.plot(t, battery, "g-", linewidth=2)
        ax2.fill_between(t, 0, battery, alpha=0.3, color="green")
        ax2.axhline(0, color="r", linestyle="--", linewidth=2, label="Empty")

        ax2.set_xlabel("Time (s)", fontsize=12)
        ax2.set_ylabel("Battery Energy (Wh)", fontsize=12)
        ax2.set_title(f"{mission_name} - Battery State", fontsize=14, fontweight="bold")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best")

        battery_file = output_dir / "battery_state.png"
        fig2.savefig(battery_file, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        plot_files["battery_state"] = battery_file

    # --- Plot 3: Combined Dashboard ---
    if battery is not None:
        fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(16, 6))

        # Left: Flight path
        ax3a.plot(x, y, "b-", linewidth=2, alpha=0.7)
        ax3a.plot(x[0], y[0], "go", markersize=10, label="Start")
        if len(wp_x) > 1:
            ax3a.plot(wp_x[1:], wp_y[1:], "r^", markersize=8, label="Waypoints")
        ax3a.set_xlabel("X Position (m)")
        ax3a.set_ylabel("Y Position (m)")
        ax3a.set_title("Flight Path")
        ax3a.grid(True, alpha=0.3)
        ax3a.legend()
        ax3a.axis("equal")

        # Right: Battery
        ax3b.plot(t, battery, "g-", linewidth=2)
        ax3b.fill_between(t, 0, battery, alpha=0.3, color="green")
        ax3b.axhline(0, color="r", linestyle="--", linewidth=1.5)
        ax3b.set_xlabel("Time (s)")
        ax3b.set_ylabel("Battery Energy (Wh)")
        ax3b.set_title("Battery State Over Time")
        ax3b.grid(True, alpha=0.3)

        fig3.suptitle(f"{mission_name} - Mission Overview", fontsize=16, fontweight="bold")
        fig3.tight_layout()

        overview_file = output_dir / "mission_overview.png"
        fig3.savefig(overview_file, dpi=150, bbox_inches="tight")
        plt.close(fig3)
        plot_files["mission_overview"] = overview_file

    return plot_files
