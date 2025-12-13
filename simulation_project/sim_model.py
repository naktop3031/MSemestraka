"""
Core simulation logic.
"""
import simpy
from .entities import Tray
from .resources import FarmResources
from .config import (
    TRAY_GENERATION_INTERVAL, PLANTING_DURATION, 
    GROWTH_DURATION, HARVEST_DURATION, 
    DISTANCE_STATION_TO_SHELF, SIM_TIME
)

class FarmSimulation:
    def __init__(self, config_scenario):
        self.env = simpy.Environment()
        self.config = config_scenario
        self.resources = FarmResources(self.env, self.config)
        
        # Stats
        self.trays_completed = 0
        self.tray_wait_times = [] # list of seconds
        self.agv_utilization = {i: 0.0 for i in range(config_scenario["AGV_COUNT"])}
        
    def log(self, message):
        # Optional: Print logs if needed, or keeping it clean for stats
        # print(f"[{self.env.now:.1f}] {message}")
        pass

    def run(self):
        self.env.process(self.tray_generator())
        self.env.run(until=SIM_TIME)
        
        # Post-run stats calculation
        for agv in self.resources.agvs:
            self.agv_utilization[agv.id] = agv.utilization_time / SIM_TIME

    def tray_generator(self):
        """Generates new trays entering the system."""
        tray_id = 0
        while True:
            yield self.env.timeout(TRAY_GENERATION_INTERVAL)
            tray_id += 1
            tray = Tray(tray_id, self.env.now)
            self.env.process(self.lifecycle_process(tray))

    def request_agv_task(self, description, target_pos, tray=None):
        """Helper to Request AGV, Move, and Release."""
        req_start = self.env.now
        
        # 1. Request an AGV from the fleet store
        agv = yield self.resources.agv_fleet.get()
        
        wait_time = self.env.now - req_start
        self.tray_wait_times.append(wait_time)
        
        # 2. AGV travels TO the current location of the task? 
        # In this simplified model, we assume AGV is 'here' or we don't simulate the 'move to pickup' explicitly separate from 'transport'.
        # But to be robust:
        # Move AGV to 'start' (where the tray is)? 
        # For simplicity, let's assume the AGV teleports to pickup or we just simulate the transport leg.
        # Let's improve: The AGV is at agv.pos. The Tray is at a 'source' pos.
        # But `request_agv_task` is called from inside a process (Planting or Shelf).
        # We need to know where we are.
        
        # Let's simplify: This function will simulate the Transport leg ONLY.
        # The AGV 'moves' from wherever it is to 'target_pos'.
        
        if tray:
            agv.carrying_tray = tray
        
        yield self.env.process(agv.move(target_pos, description))
        
        if tray:
            agv.carrying_tray = None
        
        # 3. Release AGV back to fleet
        yield self.resources.agv_fleet.put(agv)
        
        return agv

    def lifecycle_process(self, tray):
        """
        Lifecycle of a Tray:
        1. Spawn -> Wait for Planting Station
        2. Plant (Process)
        3. Transport to Shelf (AGV)
        4. Grow (Timeout)
        5. Transport to Harvest (AGV)
        6. Harvest (Process) -> Done
        """
        from .config import PLANTING_POS, SHELF_POS, HARVEST_POS
        
        # --- STAGE 1: PLANTING ---
        # Request Planting Station
        with self.resources.planting_stations.request() as req:
            yield req
            # Planting process
            yield self.env.timeout(PLANTING_DURATION)
            tray.is_planted = True
            tray.planted_time = self.env.now
            self.log(f"{tray} planted.")

        # --- STAGE 2: TRANSPORT TO SHELF ---
        # Request AGV to move Tray from PLanting (PLANTING_POS) to Shelf (SHELF_POS)
        # Note: In a real sim, we'd move AGV to Planting Pos first. 
        # For this visualizer, let's make the AGV move from its current pos to SHELF_POS.
        yield self.env.process(self.request_agv_task("To Shelf", SHELF_POS, tray))
        
        # Put in Shelf (Resource/Container)
        yield self.resources.shelves.put(1) # Identify space usage
        
        # --- STAGE 3: GROWING ---
        yield self.env.timeout(GROWTH_DURATION)
        tray.is_grown = True
        self.log(f"{tray} grown.")

        # --- STAGE 4: TRANSPORT TO HARVEST ---
        # Request AGV to move Tray from Shelf to Harvest Station
        yield self.env.process(self.request_agv_task("To Harvest", HARVEST_POS, tray))
        
        # Remove from Shelf
        yield self.resources.shelves.get(1)

        # --- STAGE 5: HARVEST ---
        with self.resources.harvest_stations.request() as req:
            yield req
            yield self.env.timeout(HARVEST_DURATION)
            tray.harvest_completed_time = self.env.now
            self.trays_completed += 1
            self.log(f"{tray} harvested and shipping.")
