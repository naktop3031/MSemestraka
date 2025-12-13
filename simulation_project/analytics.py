"""
Analytics and Visualization.
"""
import matplotlib.pyplot as plt
import pandas as pd
import os
import numpy as np

class Analytics:
    def __init__(self):
        self.results = {} # {scenario_name: stats_dict}

    def add_result(self, scenario_name, simulation_obj):
        stats = {
            "trays_completed": simulation_obj.trays_completed,
            "avg_wait_time": np.mean(simulation_obj.tray_wait_times) if simulation_obj.tray_wait_times else 0,
            "agv_utilization": np.mean(list(simulation_obj.agv_utilization.values())) * 100, # percent
            "raw_wait_times": simulation_obj.tray_wait_times
        }
        self.results[scenario_name] = stats

    def print_summary(self):
        print("\n=== SIMULATION RESULTS ===")
        for name, stats in self.results.items():
            print(f"Scenario: {name}")
            print(f"  - Trays Completed: {stats['trays_completed']}")
            print(f"  - Avg AGV Wait Time: {stats['avg_wait_time']:.2f} s")
            print(f"  - Avg AGV Utilization: {stats['agv_utilization']:.1f}%")
            print("-" * 30)

    def generate_graphs(self, output_dir="results"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        scenarios = list(self.results.keys())
        completed = [self.results[s]["trays_completed"] for s in scenarios]
        waits = [self.results[s]["avg_wait_time"] for s in scenarios]
        utils = [self.results[s]["agv_utilization"] for s in scenarios]

        # 1. Throughput Comparison
        plt.figure(figsize=(10, 6))
        plt.bar(scenarios, completed, color=['red', 'green'])
        plt.title('Throughput: Trays Completed (8h)')
        plt.ylabel('Trays')
        plt.savefig(f"{output_dir}/throughput_comparison.png")
        plt.close()

        # 2. Average Wait Time Comparison
        plt.figure(figsize=(10, 6))
        plt.bar(scenarios, waits, color=['red', 'green'])
        plt.title('Average AGV Wait Time')
        plt.ylabel('Seconds')
        plt.savefig(f"{output_dir}/wait_time_comparison.png")
        plt.close()

        # 3. Utilization Comparison
        plt.figure(figsize=(10, 6))
        plt.bar(scenarios, utils, color=['blue', 'orange'])
        plt.title('Average AGV Utilization')
        plt.ylabel('Utilization (%)')
        plt.ylim(0, 100)
        plt.savefig(f"{output_dir}/utilization_comparison.png")
        plt.close()
        
        print(f"Graphs saved to {os.path.abspath(output_dir)}")
