"""
Configuration constants for the Vertical Farm Simulation.
"""

# Simulation Time Unit: Seconds
# Simulation Time Unit: Seconds
SIM_TIME = 7200  # 2 hours
FPS = 60 # Visualizer FPS

# Layout / Visuals
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 1080
PLANTING_POS = (100, 100)
SHELF_POS = (400, 300)
HARVEST_POS = (100, 500)
AGV_START_POS = (400, 500)

# Farm Physics / Timing (in seconds)
TRAY_GENERATION_INTERVAL = 25  # New tray every 25 seconds (Bottleneck test: 4 AGVs needed)
PLANTING_DURATION = 30
GROWTH_DURATION = 120  # Fast growth for demo (2 minutes)
HARVEST_DURATION = 40
AGV_MOVE_SPEED = 1.0  # Meters per second
DISTANCE_STATION_TO_SHELF = 50  # Meters

# Battery specification (optional complexity)
BATTERY_CAPACITY = 100.0
CHARGE_RATE = 2.0
DISCHARGE_RATE_MOVE = 0.5
DISCHARGE_RATE_IDLE = 0.05

# Scenarios
# Scenario A: Bottlenecked (Too few robots)
SCENARIO_A = {
    "NAME": "Scenario A (Baseline)",
    "AGV_COUNT": 2,
    "PLANTING_STATIONS": 1,
    "HARVEST_STATIONS": 1,
    "SHELF_CAPACITY": 1000
}

# Scenario B: Optimized (More robots, maybe more stations)
SCENARIO_B = {
    "NAME": "Scenario B (Optimized)",
    "AGV_COUNT": 5,
    "PLANTING_STATIONS": 2,
    "HARVEST_STATIONS": 2,
    "SHELF_CAPACITY": 1000
}
