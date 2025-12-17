"""
Multi-Round Simulation Analysis
Runs 20 rounds of each scenario (Reactive vs Proactive) and generates comparison graphs.
"""

import simpy
import random
import math
import matplotlib.pyplot as plt
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

# ==========================================
# CONFIGURATION (Same as complete-script.py)
# ==========================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Simulation Constants
AGV_SPEED = 2.0
FIX_VEHICLE_SPEED = 3.5
BATTERY_DRAIN = 0.05
CHARGE_SPEED = 0.5
HARVEST_TIME = 60
UNLOAD_TIME = 40
REPAIR_TIME = 100

# Functionality / Wear Constants
FUNC_DECAY_BASE = 0.04
FUNC_DECAY_VAR = 0.3

AGV_COUNT = 3
HARVEST_POINTS_COUNT = 15

# Number of rounds to run
NUM_ROUNDS = 20

# ==========================================
# CLASSES (Headless versions - no Pygame)
# ==========================================

@dataclass
class Location:
    x: float
    y: float

class HarvestPoint:
    def __init__(self, id, x, y):
        self.id = id
        self.location = Location(x, y)
        self.items = 10
        self.is_empty = False
        self.claimed_by = None

    def harvest(self):
        if self.items > 0:
            self.items = 0
            self.is_empty = True
            return 10
        return 0

class AGV:
    def __init__(self, env, id, start_x, start_y, storage_loc, charger_loc, strategy):
        self.env = env
        self.id = id
        self.location = Location(start_x, start_y)
        self.storage_loc = storage_loc
        self.charger_loc = charger_loc
        self.strategy = strategy
        
        self.battery = 100.0
        self.functionality = 100.0
        
        quality_factor = random.uniform(0.5, 1.5)
        self.my_decay_rate = FUNC_DECAY_BASE * quality_factor
        
        self.state = "IDLE"
        self.items_carried = 0
        self.total_harvested = 0
        self.distance_traveled = 0
        self.target: Optional[Location] = None
        self.current_harvest_point: Optional[HarvestPoint] = None
        
        self.action = env.process(self.run())

    def get_distance(self, loc1, loc2):
        return math.sqrt((loc1.x - loc2.x)**2 + (loc1.y - loc2.y)**2)

    def move_towards(self, target_loc):
        if self.battery <= 0 or self.state == "BROKEN":
            return False

        dx = target_loc.x - self.location.x
        dy = target_loc.y - self.location.y
        dist = math.sqrt(dx**2 + dy**2)
        
        move_dist = min(dist, AGV_SPEED)
        cost = move_dist * BATTERY_DRAIN

        if self.battery - cost <= 0:
            self.battery = 0
            return False 
        
        if dist <= AGV_SPEED:
            self.location.x = target_loc.x
            self.location.y = target_loc.y
            self.distance_traveled += dist
            self.battery -= cost
            return True 
        else:
            move_x = (dx / dist) * AGV_SPEED
            move_y = (dy / dist) * AGV_SPEED
            self.location.x += move_x
            self.location.y += move_y
            self.distance_traveled += AGV_SPEED
            self.battery -= cost
            return False 

    def run(self):
        while True:
            if self.state != "DEAD" and self.state != "BROKEN":
                variance = random.uniform(1.0 - FUNC_DECAY_VAR, 1.0 + FUNC_DECAY_VAR)
                decay = self.my_decay_rate * variance
                self.functionality -= decay
                
                if self.functionality <= 0:
                    self.functionality = 0
                    self.state = "BROKEN"
                    if self.current_harvest_point and self.current_harvest_point.claimed_by == self.id:
                        self.current_harvest_point.claimed_by = None
            
            if self.state == "DEAD":
                yield self.env.timeout(1)
                continue

            if self.state == "BROKEN":
                yield self.env.timeout(1)
                continue

            if self.state not in ["CHARGING", "MOVING_TO_CHARGER", "IDLE", "DEAD", "BROKEN"]:
                dist_home = self.get_distance(self.location, self.charger_loc)
                min_needed = (dist_home * BATTERY_DRAIN) + 2.0 
                
                if self.battery < min_needed:
                    self.state = "MOVING_TO_CHARGER"
                    self.target = self.charger_loc
                    if self.current_harvest_point and self.current_harvest_point.claimed_by == self.id:
                        self.current_harvest_point.claimed_by = None
                        self.current_harvest_point = None

            if self.state == "IDLE":
                if self.items_carried > 0:
                    self.state = "MOVING_TO_STORAGE"
                    self.target = self.storage_loc
                    yield self.env.timeout(1)
                    continue 

                decision = self.strategy(self)
                
                if decision == "CHARGE":
                    self.state = "MOVING_TO_CHARGER"
                    self.target = self.charger_loc
                
                elif isinstance(decision, HarvestPoint):
                    self.state = "MOVING_TO_HARVEST"
                    self.current_harvest_point = decision
                    self.target = decision.location
                
                else:
                    yield self.env.timeout(1)

            elif self.state == "MOVING_TO_HARVEST":
                arrived = self.move_towards(self.target)
                if arrived:
                    self.state = "HARVESTING"
                yield self.env.timeout(1)

            elif self.state == "HARVESTING":
                yield self.env.timeout(HARVEST_TIME)
                if self.state != "BROKEN" and self.battery > 0:
                    amount = self.current_harvest_point.harvest()
                    self.items_carried = amount
                    self.state = "MOVING_TO_STORAGE"
                    self.target = self.storage_loc

            elif self.state == "MOVING_TO_STORAGE":
                arrived = self.move_towards(self.target)
                if arrived:
                    self.state = "UNLOADING"
                yield self.env.timeout(1)

            elif self.state == "UNLOADING":
                yield self.env.timeout(UNLOAD_TIME)
                self.total_harvested += self.items_carried
                self.items_carried = 0
                self.state = "IDLE"
                self.current_harvest_point = None

            elif self.state == "MOVING_TO_CHARGER":
                arrived = self.move_towards(self.target)
                if arrived:
                    self.state = "CHARGING"
                yield self.env.timeout(1)

            elif self.state == "CHARGING":
                self.battery += CHARGE_SPEED
                if self.battery >= 100:
                    self.battery = 100
                    self.state = "IDLE"
                yield self.env.timeout(1)
            
            else:
                yield self.env.timeout(1)

class FixVehicle:
    def __init__(self, env, start_x, start_y, agvs, strategy):
        self.env = env
        self.location = Location(start_x, start_y)
        self.home_loc = Location(start_x, start_y)
        self.agvs = agvs
        self.strategy = strategy
        self.state = "IDLE"
        self.target_agv: Optional[AGV] = None
        self.action = env.process(self.run())

    def get_distance(self, loc1, loc2):
        return math.sqrt((loc1.x - loc2.x)**2 + (loc1.y - loc2.y)**2)

    def move_towards(self, target_loc):
        dx = target_loc.x - self.location.x
        dy = target_loc.y - self.location.y
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist <= FIX_VEHICLE_SPEED:
            self.location.x = target_loc.x
            self.location.y = target_loc.y
            return True
        else:
            move_x = (dx / dist) * FIX_VEHICLE_SPEED
            move_y = (dy / dist) * FIX_VEHICLE_SPEED
            self.location.x += move_x
            self.location.y += move_y
            return False

    def run(self):
        while True:
            if self.state == "IDLE":
                target = self.strategy(self, self.agvs)
                if target:
                    self.target_agv = target
                    self.state = "MOVING_TO_TARGET"
                else:
                    yield self.env.timeout(1)

            elif self.state == "MOVING_TO_TARGET":
                arrived = self.move_towards(self.target_agv.location)
                
                if arrived:
                    if self.target_agv.state == "BROKEN":
                        self.state = "REPAIRING"
                    else:
                        if self.target_agv.functionality <= 1.0: 
                             self.state = "REPAIRING"
                        else:
                             yield self.env.timeout(1)
                else:
                    yield self.env.timeout(1)

            elif self.state == "REPAIRING":
                yield self.env.timeout(REPAIR_TIME)
                self.target_agv.functionality = 100.0
                self.target_agv.state = "IDLE"
                self.target_agv = None
                self.state = "RETURNING"

            elif self.state == "RETURNING":
                arrived = self.move_towards(self.home_loc)
                if arrived:
                    self.state = "IDLE"
                yield self.env.timeout(1)

# ==========================================
# STRATEGIES
# ==========================================

def agv_strategy_random_safe(agv):
    points = [p for p in agv.env_context['points'] if not p.is_empty]
    if not points: return None
    random.shuffle(points)
    for p in points:
        dist_to_point = agv.get_distance(agv.location, p.location)
        dist_point_to_home = agv.get_distance(p.location, agv.charger_loc)
        total_trip_cost = (dist_to_point + dist_point_to_home) * BATTERY_DRAIN
        if agv.battery > (total_trip_cost + 5.0): return p
    return "CHARGE"

def agv_strategy_smart(agv):
    available_points = [p for p in agv.env_context['points'] if not p.is_empty and p.claimed_by is None]
    if not available_points: return None
    best_point = min(available_points, key=lambda p: agv.get_distance(agv.location, p.location))
    dist_to_point = agv.get_distance(agv.location, best_point.location)
    dist_point_to_storage = agv.get_distance(best_point.location, agv.storage_loc)
    dist_storage_to_charger = agv.get_distance(agv.storage_loc, agv.charger_loc)
    total_mission_dist = dist_to_point + dist_point_to_storage + dist_storage_to_charger
    required_battery = (total_mission_dist * BATTERY_DRAIN) + 10
    if agv.battery < required_battery: return "CHARGE"
    else:
        best_point.claimed_by = agv.id
        return best_point

def fix_strategy_reactive(fixer, agvs):
    broken = [a for a in agvs if a.state == "BROKEN"]
    if broken:
        return min(broken, key=lambda a: fixer.get_distance(fixer.location, a.location))
    return None

def fix_strategy_proactive(fixer, agvs):
    broken = [a for a in agvs if a.state == "BROKEN"]
    if broken:
        return min(broken, key=lambda a: fixer.get_distance(fixer.location, a.location))
    
    for agv in agvs:
        if agv.state == "DEAD": continue
        
        dist = fixer.get_distance(fixer.location, agv.location)
        travel_time = dist / FIX_VEHICLE_SPEED
        
        time_to_failure = agv.functionality / agv.my_decay_rate
        
        if time_to_failure < (travel_time + 100): 
            return agv
            
    return None

# ==========================================
# HEADLESS SIMULATION
# ==========================================

def run_scenario_headless(scenario_name, agv_strategy, fix_strategy, max_time=50000):
    """Run a single simulation round without visualization."""
    env = simpy.Environment()
    
    storage_loc = Location(50, 50)
    charger_loc = Location(SCREEN_WIDTH - 50, 50)
    fix_station_loc = Location(50, SCREEN_HEIGHT - 50)
    
    harvest_points = []
    rows = 3
    cols = 5
    for r in range(rows):
        for c in range(cols):
            x = 150 + c * 120
            y = 150 + r * 120
            harvest_points.append(HarvestPoint(len(harvest_points), x, y))

    env_context = {'points': harvest_points}

    agvs = []
    for i in range(AGV_COUNT):
        agv = AGV(env, i, 50, 50 + (i*30), storage_loc, charger_loc, agv_strategy)
        agv.env_context = env_context
        agvs.append(agv)

    fix_vehicle = FixVehicle(env, fix_station_loc.x, fix_station_loc.y, agvs, fix_strategy)

    sim_time = 0
    
    while sim_time < max_time:
        all_harvested = all(p.is_empty for p in harvest_points)
        all_home = all(agv.state in ["IDLE", "CHARGING", "DEAD"] for agv in agvs)
        dead_count = sum(1 for a in agvs if a.state == "DEAD")
        all_dead = (dead_count == AGV_COUNT)

        if (all_harvested and all_home) or all_dead:
            break 

        env.run(until=sim_time + 1)
        sim_time += 1

    total_dist = sum(a.distance_traveled for a in agvs)
    total_items = sum(a.total_harvested for a in agvs)
    dead_agvs = sum(1 for a in agvs if a.state == "DEAD")
    
    stats = {
        "Scenario": scenario_name,
        "Total Time": sim_time,
        "Total Distance": total_dist,
        "Items Harvested": total_items,
        "Dead AGVs": dead_agvs,
        "Efficiency": total_dist / total_items if total_items > 0 else 0
    }
    
    return stats

def run_multiple_rounds(num_rounds=NUM_ROUNDS):
    """Run multiple rounds of both scenarios and collect statistics."""
    reactive_results = []
    proactive_results = []
    
    print(f"Running {num_rounds} rounds of each scenario...\n")
    
    for i in range(num_rounds):
        print(f"Round {i+1}/{num_rounds}...", end=" ")
        
        # Run reactive scenario
        stats1 = run_scenario_headless(
            "Reactive Fixer", 
            agv_strategy_random_safe, 
            fix_strategy_reactive
        )
        reactive_results.append(stats1)
        
        # Run proactive scenario
        stats2 = run_scenario_headless(
            "Proactive Fixer", 
            agv_strategy_smart, 
            fix_strategy_proactive
        )
        proactive_results.append(stats2)
        
        print(f"Reactive: {stats1['Total Time']}t, {stats1['Total Distance']:.0f}px | "
              f"Proactive: {stats2['Total Time']}t, {stats2['Total Distance']:.0f}px")
    
    return reactive_results, proactive_results

def generate_graphs(reactive_results, proactive_results, output_dir="."):
    """Generate comparison graphs for Total Time and Distance."""
    
    rounds = range(1, len(reactive_results) + 1)
    
    reactive_times = [r['Total Time'] for r in reactive_results]
    proactive_times = [r['Total Time'] for r in proactive_results]
    
    reactive_distances = [r['Total Distance'] for r in reactive_results]
    proactive_distances = [r['Total Distance'] for r in proactive_results]
    
    # Set up the figure with 2 subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Reactive vs Proactive Fixer Strategy Comparison\n(20 Rounds)', fontsize=14, fontweight='bold')
    
    # ===== Graph 1: Total Time per Round (Line Chart) =====
    ax1 = axes[0, 0]
    ax1.plot(rounds, reactive_times, 'o-', color='#e74c3c', label='Reactive Fixer', linewidth=2, markersize=6)
    ax1.plot(rounds, proactive_times, 's-', color='#3498db', label='Proactive Fixer', linewidth=2, markersize=6)
    ax1.fill_between(rounds, reactive_times, alpha=0.2, color='#e74c3c')
    ax1.fill_between(rounds, proactive_times, alpha=0.2, color='#3498db')
    ax1.set_xlabel('Round', fontsize=11)
    ax1.set_ylabel('Total Time (ticks)', fontsize=11)
    ax1.set_title('Total Time per Round', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(rounds)
    
    # ===== Graph 2: Total Distance per Round (Line Chart) =====
    ax2 = axes[0, 1]
    ax2.plot(rounds, reactive_distances, 'o-', color='#e74c3c', label='Reactive Fixer', linewidth=2, markersize=6)
    ax2.plot(rounds, proactive_distances, 's-', color='#3498db', label='Proactive Fixer', linewidth=2, markersize=6)
    ax2.fill_between(rounds, reactive_distances, alpha=0.2, color='#e74c3c')
    ax2.fill_between(rounds, proactive_distances, alpha=0.2, color='#3498db')
    ax2.set_xlabel('Round', fontsize=11)
    ax2.set_ylabel('Total Distance (pixels)', fontsize=11)
    ax2.set_title('Total Distance per Round', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(rounds)
    
    # ===== Graph 3: Average Comparison Bar Chart =====
    ax3 = axes[1, 0]
    
    avg_reactive_time = np.mean(reactive_times)
    avg_proactive_time = np.mean(proactive_times)
    avg_reactive_dist = np.mean(reactive_distances)
    avg_proactive_dist = np.mean(proactive_distances)
    
    std_reactive_time = np.std(reactive_times)
    std_proactive_time = np.std(proactive_times)
    std_reactive_dist = np.std(reactive_distances)
    std_proactive_dist = np.std(proactive_distances)
    
    x = np.arange(2)
    width = 0.35
    
    bars1 = ax3.bar(x - width/2, [avg_reactive_time, avg_reactive_dist], width, 
                    yerr=[std_reactive_time, std_reactive_dist],
                    label='Reactive Fixer', color='#e74c3c', capsize=5)
    bars2 = ax3.bar(x + width/2, [avg_proactive_time, avg_proactive_dist], width,
                    yerr=[std_proactive_time, std_proactive_dist],
                    label='Proactive Fixer', color='#3498db', capsize=5)
    
    ax3.set_ylabel('Value', fontsize=11)
    ax3.set_title('Average Metrics (with Std Dev)', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(['Avg Total Time\n(ticks)', 'Avg Total Distance\n(pixels)'])
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, val in zip(bars1, [avg_reactive_time, avg_reactive_dist]):
        ax3.annotate(f'{val:.0f}', xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
    for bar, val in zip(bars2, [avg_proactive_time, avg_proactive_dist]):
        ax3.annotate(f'{val:.0f}', xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
    
    # ===== Graph 4: Box Plot Comparison =====
    ax4 = axes[1, 1]
    
    box_data_time = [reactive_times, proactive_times]
    box_data_dist = [reactive_distances, proactive_distances]
    
    positions_time = [1, 2]
    positions_dist = [4, 5]
    
    bp1 = ax4.boxplot(box_data_time, positions=positions_time, widths=0.6, patch_artist=True)
    bp2 = ax4.boxplot(box_data_dist, positions=positions_dist, widths=0.6, patch_artist=True)
    
    colors = ['#e74c3c', '#3498db']
    for i, (box1, box2) in enumerate(zip(bp1['boxes'], bp2['boxes'])):
        box1.set_facecolor(colors[i])
        box1.set_alpha(0.7)
        box2.set_facecolor(colors[i])
        box2.set_alpha(0.7)
    
    ax4.set_xticks([1.5, 4.5])
    ax4.set_xticklabels(['Total Time\n(ticks)', 'Total Distance\n(pixels)'])
    ax4.set_title('Distribution Comparison (Box Plot)', fontsize=12, fontweight='bold')
    ax4.legend([bp1['boxes'][0], bp1['boxes'][1]], ['Reactive', 'Proactive'], loc='upper right')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    # Save the figure
    output_path = f"{output_dir}/simulation_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\nGraph saved to: {output_path}")
    
    plt.show()
    
    return output_path

def print_summary_stats(reactive_results, proactive_results):
    """Print summary statistics for both scenarios."""
    reactive_times = [r['Total Time'] for r in reactive_results]
    proactive_times = [r['Total Time'] for r in proactive_results]
    reactive_distances = [r['Total Distance'] for r in reactive_results]
    proactive_distances = [r['Total Distance'] for r in proactive_results]
    
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    
    print(f"\n{'Metric':<25} | {'Reactive Fixer':<20} | {'Proactive Fixer':<20}")
    print("-" * 70)
    
    print(f"{'Avg Total Time (ticks)':<25} | {np.mean(reactive_times):<20.2f} | {np.mean(proactive_times):<20.2f}")
    print(f"{'Std Dev Time':<25} | {np.std(reactive_times):<20.2f} | {np.std(proactive_times):<20.2f}")
    print(f"{'Min Time':<25} | {np.min(reactive_times):<20} | {np.min(proactive_times):<20}")
    print(f"{'Max Time':<25} | {np.max(reactive_times):<20} | {np.max(proactive_times):<20}")
    print("-" * 70)
    print(f"{'Avg Distance (px)':<25} | {np.mean(reactive_distances):<20.2f} | {np.mean(proactive_distances):<20.2f}")
    print(f"{'Std Dev Distance':<25} | {np.std(reactive_distances):<20.2f} | {np.std(proactive_distances):<20.2f}")
    print(f"{'Min Distance':<25} | {np.min(reactive_distances):<20.2f} | {np.min(proactive_distances):<20.2f}")
    print(f"{'Max Distance':<25} | {np.max(reactive_distances):<20.2f} | {np.max(proactive_distances):<20.2f}")
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    
    time_diff = np.mean(reactive_times) - np.mean(proactive_times)
    dist_diff = np.mean(reactive_distances) - np.mean(proactive_distances)
    
    if time_diff > 0:
        print(f"✓ Proactive strategy is faster by {time_diff:.1f} ticks on average ({100*time_diff/np.mean(reactive_times):.1f}% improvement)")
    else:
        print(f"✗ Reactive strategy is faster by {-time_diff:.1f} ticks on average")
    
    if dist_diff > 0:
        print(f"✓ Proactive strategy uses less distance by {dist_diff:.1f} px on average ({100*dist_diff/np.mean(reactive_distances):.1f}% improvement)")
    else:
        print(f"✗ Reactive strategy uses less distance by {-dist_diff:.1f} px on average")

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("MULTI-ROUND SIMULATION ANALYSIS")
    print("="*70)
    print(f"Configuration: {NUM_ROUNDS} rounds, {AGV_COUNT} AGVs, {HARVEST_POINTS_COUNT} harvest points")
    print("="*70 + "\n")
    
    # Run simulations
    reactive_results, proactive_results = run_multiple_rounds(NUM_ROUNDS)
    
    # Print summary
    print_summary_stats(reactive_results, proactive_results)
    
    # Generate graphs
    generate_graphs(reactive_results, proactive_results)
