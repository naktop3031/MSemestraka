"""
Resources (Agents/Robots/Machinery) in the simulation.
"""
import simpy
from .config import AGV_MOVE_SPEED, DISTANCE_STATION_TO_SHELF

class AGV:
    """
    Automated Guided Vehicle.
    States: IDLE, MOVING_TO_TASK, TRANSPORTING, RETURNING
    """
    def __init__(self, env, id, start_pos):
        self.env = env
        self.id = id
        self.resource = simpy.Resource(env, capacity=1)
        self.state = "IDLE"
        self.total_distance_traveled = 0.0
        self.tasks_completed = 0
        self.utilization_time = 0.0
        
        # Animation State
        self.pos = start_pos # Current (x, y) tuple
        self.target_pos = start_pos
        self.move_start_time = 0
        self.move_duration = 0
        self.carrying_tray = None # Reference to Tray object if carrying

    def move(self, target_pos, description="Moving"):
        """Simulate travel time to a specific 2D coordinate."""
        # Calculate distance
        dist = ((target_pos[0] - self.pos[0])**2 + (target_pos[1] - self.pos[1])**2)**0.5
        travel_time = dist / AGV_MOVE_SPEED
        
        # Setup Animation
        self.target_pos = target_pos
        self.move_start_time = self.env.now
        self.move_duration = travel_time
        self.state = f"MOVING ({description})"
        
        yield self.env.timeout(travel_time)
        
        # Arrival
        duration = self.env.now - self.move_start_time
        self.utilization_time += duration
        self.total_distance_traveled += dist
        self.pos = target_pos
        self.state = "IDLE"

    def __repr__(self):
        return f"AGV_{self.id}"

class FarmResources:
    """
    Container for all system resources.
    """
    def __init__(self, env, config):
        self.env = env
        # Machines
        self.planting_stations = simpy.Resource(env, capacity=config["PLANTING_STATIONS"])
        self.harvest_stations = simpy.Resource(env, capacity=config["HARVEST_STATIONS"])
        
        # Storage
        self.shelves = simpy.Container(env, capacity=config["SHELF_CAPACITY"], init=0)
        
        # Fleet of AGVs (We use a FilterStore or just a list of Resources for manual selection, 
        # but standard simpy.Resource(capacity=N) is easier if all are identical.
        # However, to track individual AGV stats, we need object instances.)
        # We will use a Store to request a specific AGV object.
        self.agv_fleet = simpy.Store(env)
        self.agvs = []
        from .config import AGV_START_POS
        for i in range(config["AGV_COUNT"]):
            # Offset start pos slightly so they don't overlap perfectly
            start_pos = (AGV_START_POS[0] + i*10, AGV_START_POS[1]) 
            agv = AGV(env, i, start_pos)
            self.agvs.append(agv)
            self.agv_fleet.put(agv)
