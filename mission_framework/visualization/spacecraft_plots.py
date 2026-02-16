"""
Spacecraft mission plotting utilities.
Generates visualizations for mission schedules, timelines, and operations.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import json

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from mission_framework.core.types import Plan, SimResult


def plot_spacecraft_mission(
    plan: Plan,
    sim_result: SimResult,
    output_dir: Path,
    mission_name: str = "Spacecraft Mission"
) -> Dict[str, Path]:
    """
    Generate plots for spacecraft mission.
    
    Args:
        plan: Mission plan with schedule
        sim_result: Simulation result with trajectory
        output_dir: Directory to save plots
        mission_name: Name for plot titles
        
    Returns:
        Dictionary mapping plot names to file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_files = {}
    
    # Extract schedule from plan
    if not plan.schedule:
        return plot_files
    
    # Handle both Schedule objects and lists
    if hasattr(plan.schedule, 'events'):
        schedule = plan.schedule.events
    else:
        schedule = plan.schedule
    
    if not schedule or len(schedule) == 0:
        return plot_files
    
    # Convert schedule to lists for plotting
    event_labels = []
    event_types = []
    start_times = []
    end_times = []
    durations = []
    
    for event in schedule:
        # Handle both Event objects and dictionaries
        if hasattr(event, 'label'):
            label = event.label or 'Unknown'
            etype = event.etype
            t_start = float(event.t_start)
            t_end = float(event.t_end)
        else:
            label = event.get('label', 'Unknown')
            etype = event.get('etype', 'unknown')
            t_start = float(event.get('t_start', 0))
            t_end = float(event.get('t_end', t_start))
        
        # Clean up event type string
        if 'EventType.' in str(etype):
            etype = str(etype).replace('EventType.', '').lower()
        else:
            etype = str(etype).lower()
        
        event_labels.append(label)
        event_types.append(etype)
        start_times.append(t_start)
        end_times.append(t_end)
        durations.append(t_end - t_start)
    
    # --- Plot 1: Mission Timeline (Gantt Chart) ---
    fig1, ax1 = plt.subplots(figsize=(14, 8))
    
    # Color mapping for event types
    color_map = {
        'observation': '#FF6B6B',  # Red
        'downlink': '#4ECDC4',      # Teal
        'idle': '#95A5A6',          # Gray
        'charging': '#F39C12',      # Orange
    }
    
    # Track unique event types for legend
    plotted_types = set()
    
    # Plot each event as a horizontal bar
    y_positions = []
    y_labels = []
    
    for i, (label, etype, t_start, duration) in enumerate(zip(event_labels, event_types, start_times, durations)):
        y_pos = len(event_labels) - i - 1  # Reverse order (earliest at top)
        y_positions.append(y_pos)
        y_labels.append(f"{i}: {label}")
        
        color = color_map.get(etype, '#BDC3C7')
        
        # Only add to legend if first occurrence of this type
        label_for_legend = etype.capitalize() if etype not in plotted_types else None
        plotted_types.add(etype)
        
        rect = Rectangle(
            (t_start, y_pos - 0.4),
            duration,
            0.8,
            facecolor=color,
            edgecolor='black',
            linewidth=0.5,
            label=label_for_legend
        )
        ax1.add_patch(rect)
        
        # Add duration text if bar is wide enough
        if duration > 0:
            duration_hours = duration / 3600
            if duration_hours > 0.5:  # Only show text for events > 30 min
                ax1.text(
                    t_start + duration / 2,
                    y_pos,
                    f'{duration_hours:.1f}h',
                    ha='center',
                    va='center',
                    fontsize=7,
                    color='white',
                    fontweight='bold'
                )
    
    ax1.set_yticks(y_positions)
    ax1.set_yticklabels(y_labels, fontsize=8)
    
    # Convert time axis to days
    max_time = max(end_times) if end_times else 604800
    ax1.set_xlim(0, max_time)
    
    # Create time ticks in days
    day_seconds = 86400
    num_days = int(np.ceil(max_time / day_seconds))
    day_ticks = [i * day_seconds for i in range(num_days + 1)]
    day_labels = [f'Day {i}' for i in range(num_days + 1)]
    
    ax1.set_xticks(day_ticks)
    ax1.set_xticklabels(day_labels, rotation=0, ha='center')
    
    ax1.set_xlabel('Mission Time', fontsize=12)
    ax1.set_ylabel('Events', fontsize=12)
    ax1.set_title(f'{mission_name} - Timeline', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')
    ax1.legend(loc='upper right', fontsize=10)
    
    timeline_file = output_dir / 'mission_timeline.png'
    fig1.savefig(timeline_file, dpi=150, bbox_inches='tight')
    plt.close(fig1)
    plot_files['mission_timeline'] = timeline_file
    
    # --- Plot 2: Operations Summary by Type ---
    fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Count events by type
    type_counts = {}
    type_durations = {}
    for etype, duration in zip(event_types, durations):
        type_counts[etype] = type_counts.get(etype, 0) + 1
        type_durations[etype] = type_durations.get(etype, 0) + duration
    
    # Sort for consistent display
    types = sorted(type_counts.keys())
    counts = [type_counts[t] for t in types]
    total_durations = [type_durations[t] / 3600 for t in types]  # Convert to hours
    colors = [color_map.get(t, '#BDC3C7') for t in types]
    
    # Left: Event count by type
    ax2a.bar(range(len(types)), counts, color=colors, edgecolor='black', linewidth=1)
    ax2a.set_xticks(range(len(types)))
    ax2a.set_xticklabels([t.capitalize() for t in types], rotation=45, ha='right')
    ax2a.set_ylabel('Number of Events', fontsize=11)
    ax2a.set_title('Event Count by Type', fontsize=12, fontweight='bold')
    ax2a.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, count in enumerate(counts):
        ax2a.text(i, count, str(count), ha='center', va='bottom', fontweight='bold')
    
    # Right: Total duration by type
    ax2b.bar(range(len(types)), total_durations, color=colors, edgecolor='black', linewidth=1)
    ax2b.set_xticks(range(len(types)))
    ax2b.set_xticklabels([t.capitalize() for t in types], rotation=45, ha='right')
    ax2b.set_ylabel('Total Duration (hours)', fontsize=11)
    ax2b.set_title('Operation Duration by Type', fontsize=12, fontweight='bold')
    ax2b.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, dur in enumerate(total_durations):
        ax2b.text(i, dur, f'{dur:.1f}h', ha='center', va='bottom', fontweight='bold')
    
    fig2.suptitle(f'{mission_name} - Operations Summary', fontsize=14, fontweight='bold')
    fig2.tight_layout()
    
    summary_file = output_dir / 'operations_summary.png'
    fig2.savefig(summary_file, dpi=150, bbox_inches='tight')
    plt.close(fig2)
    plot_files['operations_summary'] = summary_file
    
    # --- Plot 3: Daily Activity Distribution ---
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    
    # Bin events by day
    day_seconds = 86400
    max_days = int(np.ceil(max(end_times) / day_seconds)) if end_times else 7
    
    obs_per_day = [0] * max_days
    dl_per_day = [0] * max_days
    
    for etype, t_start in zip(event_types, start_times):
        day = int(t_start // day_seconds)
        if day < max_days:
            if etype == 'observation':
                obs_per_day[day] += 1
            elif etype == 'downlink':
                dl_per_day[day] += 1
    
    days = np.arange(max_days)
    width = 0.35
    
    ax3.bar(days - width/2, obs_per_day, width, label='Observations', 
            color=color_map.get('observation', '#FF6B6B'), edgecolor='black')
    ax3.bar(days + width/2, dl_per_day, width, label='Downlinks', 
            color=color_map.get('downlink', '#4ECDC4'), edgecolor='black')
    
    ax3.set_xlabel('Day', fontsize=12)
    ax3.set_ylabel('Number of Events', fontsize=12)
    ax3.set_title(f'{mission_name} - Daily Activity', fontsize=14, fontweight='bold')
    ax3.set_xticks(days)
    ax3.set_xticklabels([f'Day {i}' for i in days])
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3, axis='y')
    
    daily_file = output_dir / 'daily_activity.png'
    fig3.savefig(daily_file, dpi=150, bbox_inches='tight')
    plt.close(fig3)
    plot_files['daily_activity'] = daily_file
    
    return plot_files
