"""
Main entry point for the simulation.
"""
from .sim_model import FarmSimulation
from .config import SCENARIO_A, SCENARIO_B
from .analytics import Analytics

from .visualizer import Visualizer
import time

def run_scenario(scenario_config, enable_viz=False):
    scenario_name = scenario_config['NAME']
    print(f"\nRunning {scenario_name}...")
    print(f"  Configuration: {scenario_config['AGV_COUNT']} AGVs")
    
    sim = FarmSimulation(scenario_config)
    
    if enable_viz:
        viz = Visualizer(sim, scenario_name)
        
        # Show transition screen
        viz.show_transition_screen(f"Starting: {scenario_name}", duration=2.0)
        if not viz.running:
            return sim
        
        sim.env.process(sim.tray_generator())
        
        from .config import SIM_TIME
        
        # Real-time sync: 1 sim second = 0.001 real seconds (1000x speedup)
        # So 10000s sim time = 10 seconds real time
        REALTIME_FACTOR = 0.001  # Adjust this to slow down (higher = slower)
        
        last_sim_time = 0
        last_real_time = time.time()
        last_draw_time = 0
        
        while sim.env.peek() < SIM_TIME:
            if not viz.running:
                break
            
            sim.env.step()
            
            # Sync to real time
            sim_elapsed = sim.env.now - last_sim_time
            target_real_elapsed = sim_elapsed * REALTIME_FACTOR
            actual_real_elapsed = time.time() - last_real_time
            
            if actual_real_elapsed < target_real_elapsed:
                time.sleep(target_real_elapsed - actual_real_elapsed)
            
            last_sim_time = sim.env.now
            last_real_time = time.time()
            
            # Update GUI (Throttle to 60 FPS)
            if time.time() - last_draw_time > 0.016:
                viz.update()
                last_draw_time = time.time()

        # Post-run stats calculation
        for agv in sim.resources.agvs:
            sim.agv_utilization[agv.id] = agv.utilization_time / SIM_TIME
        
        # Show completion screen briefly (3 seconds), then continue
        print("Scenario Complete. Continuing in 3 seconds...")
        viz.show_transition_screen(f"Completed: {scenario_name}", duration=3.0)
                
    else:
        sim.run()
    
    return sim

def main():
    analytics = Analytics()
    
    # Run Baseline (WITH GUI)
    print("Starting Visualization for Scenario A (Baseline)...")
    sim_a = run_scenario(SCENARIO_A, enable_viz=True)
    analytics.add_result(SCENARIO_A["NAME"], sim_a)
    
    # Run Optimized (WITH GUI)
    print("Starting Visualization for Scenario B (Optimized)...")
    sim_b = run_scenario(SCENARIO_B, enable_viz=True)
    analytics.add_result(SCENARIO_B["NAME"], sim_b)
    
    # Report
    analytics.print_summary()
    analytics.generate_graphs()
    print("\nAll scenarios complete. Close window to exit.")
    
    # Final keep-alive - wait for user input before closing
    import pygame
    import sys
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
        time.sleep(0.016)
    
    pygame.quit()
    print("Done.")
    sys.exit(0)

if __name__ == "__main__":
    main()
