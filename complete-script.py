import simpy
import pygame
import random
import math
from dataclasses import dataclass
from typing import List, Optional, Union

# ==========================================
# CONFIGURATION
# ==========================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Simulation Constants
AGV_SPEED = 2.0
FIX_VEHICLE_SPEED = 3.5
BATTERY_DRAIN = 0.05
CHARGE_SPEED = 0.5
HARVEST_TIME = 60
UNLOAD_TIME = 40
REPAIR_TIME = 100

# Functionality / Wear Constants
FUNC_DECAY_BASE = 0.04   # Average % lost per tick
FUNC_DECAY_VAR = 0.3     # Per-tick variance (jitter)

AGV_COUNT = 3
HARVEST_POINTS_COUNT = 15

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
RED = (200, 0, 0)
BLUE = (0, 0, 200)
YELLOW = (255, 215, 0)
CYAN = (0, 255, 255)
GRAY = (100, 100, 100)
DARK_GRAY = (50, 50, 50)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
LIGHT_GRAY = (200, 200, 200)

# ==========================================
# CLASSES
# ==========================================

@dataclass
class Location:
    x: float
    y: float

class Button:
    def __init__(self, x, y, w, h, text, action_func):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.action_func = action_func
        self.font = pygame.font.SysFont("Arial", 14, bold=True)
        self.is_hovered = False

    def draw(self, screen):
        color = LIGHT_GRAY if not self.is_hovered else GRAY
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered and event.button == 1:
                self.action_func()

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
        
        # --- UNIQUE DECAY RATE ---
        # Each AGV gets a random "quality" factor.
        # Some decay at 0.5x speed (Robust), some at 1.5x speed (Fragile).
        # This ensures they break at very different times.
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
            # --- 1. WEAR AND TEAR LOGIC ---
            if self.state != "DEAD" and self.state != "BROKEN":
                # Apply per-tick jitter to the AGV's specific base rate
                variance = random.uniform(1.0 - FUNC_DECAY_VAR, 1.0 + FUNC_DECAY_VAR)
                decay = self.my_decay_rate * variance
                self.functionality -= decay
                
                if self.functionality <= 0:
                    self.functionality = 0
                    self.state = "BROKEN"
                    if self.current_harvest_point and self.current_harvest_point.claimed_by == self.id:
                        self.current_harvest_point.claimed_by = None
            
            # --- 2. CRITICAL STATES ---
            if self.state == "DEAD":
                yield self.env.timeout(1)
                continue

            if self.state == "BROKEN":
                yield self.env.timeout(1)
                continue

            # --- 3. DYNAMIC SAFETY NET ---
            if self.state not in ["CHARGING", "MOVING_TO_CHARGER", "IDLE", "DEAD", "BROKEN"]:
                dist_home = self.get_distance(self.location, self.charger_loc)
                min_needed = (dist_home * BATTERY_DRAIN) + 2.0 
                
                if self.battery < min_needed:
                    self.state = "MOVING_TO_CHARGER"
                    self.target = self.charger_loc
                    if self.current_harvest_point and self.current_harvest_point.claimed_by == self.id:
                        self.current_harvest_point.claimed_by = None
                        self.current_harvest_point = None

            # --- 4. MAIN STATE MACHINE ---
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
                        # Proactive wait
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

# --- Fix Vehicle Strategies ---

def fix_strategy_reactive(fixer, agvs):
    broken = [a for a in agvs if a.state == "BROKEN"]
    if broken:
        return min(broken, key=lambda a: fixer.get_distance(fixer.location, a.location))
    return None

def fix_strategy_proactive(fixer, agvs):
    # 1. Priority: Already broken
    broken = [a for a in agvs if a.state == "BROKEN"]
    if broken:
        return min(broken, key=lambda a: fixer.get_distance(fixer.location, a.location))
    
    # 2. Predictive Check
    for agv in agvs:
        if agv.state == "DEAD": continue
        
        dist = fixer.get_distance(fixer.location, agv.location)
        travel_time = dist / FIX_VEHICLE_SPEED
        
        # Use the AGV's SPECIFIC decay rate for accurate prediction
        time_to_failure = agv.functionality / agv.my_decay_rate
        
        if time_to_failure < (travel_time + 100): 
            return agv
            
    return None

# ==========================================
# SIMULATION MANAGER
# ==========================================

def run_scenario(scenario_name, agv_strategy, fix_strategy):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"Harvest Simulation - {scenario_name}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 14)
    title_font = pygame.font.SysFont("Arial", 20, bold=True)

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

    sim_speed = 1
    def increase_speed():
        nonlocal sim_speed
        if sim_speed < 50: sim_speed += 1
    def decrease_speed():
        nonlocal sim_speed
        if sim_speed > 0: sim_speed -= 1

    btn_y = SCREEN_HEIGHT - 40
    btn_slower = Button(SCREEN_WIDTH - 220, btn_y, 80, 30, "<< Slower", decrease_speed)
    btn_faster = Button(SCREEN_WIDTH - 100, btn_y, 80, 30, "Faster >>", increase_speed)
    buttons = [btn_slower, btn_faster]

    running = True
    sim_time = 0
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                return None
            for btn in buttons: btn.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT: increase_speed()
                elif event.key == pygame.K_LEFT: decrease_speed()
                elif event.key == pygame.K_SPACE: sim_speed = 0 if sim_speed > 0 else 1

        for _ in range(sim_speed):
            all_harvested = all(p.is_empty for p in harvest_points)
            all_home = all(agv.state == "IDLE" or agv.state == "CHARGING" or agv.state == "DEAD" for agv in agvs)
            dead_count = sum(1 for a in agvs if a.state == "DEAD")
            all_dead = (dead_count == AGV_COUNT)

            if (all_harvested and all_home) or all_dead:
                running = False
                break 

            env.run(until=sim_time + 1)
            sim_time += 1

        screen.fill(WHITE)

        pygame.draw.rect(screen, BLUE, (storage_loc.x - 20, storage_loc.y - 20, 40, 40))
        screen.blit(font.render("Storage", True, BLACK), (storage_loc.x - 20, storage_loc.y - 35))
        
        pygame.draw.rect(screen, YELLOW, (charger_loc.x - 20, charger_loc.y - 20, 40, 40))
        screen.blit(font.render("Charger", True, BLACK), (charger_loc.x - 20, charger_loc.y - 35))

        pygame.draw.rect(screen, CYAN, (fix_station_loc.x - 20, fix_station_loc.y - 20, 40, 40), 2)
        screen.blit(font.render("Service", True, BLACK), (fix_station_loc.x - 20, fix_station_loc.y + 25))

        for hp in harvest_points:
            if hp.is_empty: color = GRAY
            elif hp.claimed_by is not None: color = ORANGE
            else: color = GREEN
            pygame.draw.circle(screen, color, (hp.location.x, hp.location.y), 15)
            if hp.claimed_by is not None and not hp.is_empty:
                screen.blit(font.render(str(hp.claimed_by), True, WHITE), (hp.location.x - 5, hp.location.y - 10))

        pygame.draw.rect(screen, CYAN, (fix_vehicle.location.x - 12, fix_vehicle.location.y - 12, 24, 24))
        screen.blit(font.render("F", True, BLACK), (fix_vehicle.location.x - 4, fix_vehicle.location.y - 8))
        fix_status = f"Fixer: {fix_vehicle.state}"
        screen.blit(font.render(fix_status, True, BLACK), (fix_station_loc.x + 30, fix_station_loc.y))

        for agv in agvs:
            if agv.state == "DEAD": color = BLACK
            elif agv.state == "BROKEN": color = DARK_GRAY
            elif agv.battery < 20: color = RED
            else: color = PURPLE

            pygame.draw.rect(screen, color, (agv.location.x - 10, agv.location.y - 10, 20, 20), 2)
            
            if agv.items_carried > 0:
                pygame.draw.rect(screen, GREEN, (agv.location.x - 4, agv.location.y - 4, 8, 8))
            
            line1 = f"AGV{agv.id}|{int(agv.battery)}%|{agv.state}"
            line2 = f"Func: {int(agv.functionality)}%"
            
            screen.blit(font.render(line1, True, BLACK), (agv.location.x + 15, agv.location.y - 15))
            func_color = RED if agv.functionality < 20 else BLACK
            screen.blit(font.render(line2, True, func_color), (agv.location.x + 15, agv.location.y))

        screen.blit(font.render(f"Time: {sim_time}", True, BLACK), (10, SCREEN_HEIGHT - 30))
        speed_text = f"Speed: {sim_speed}x" if sim_speed > 0 else "Speed: PAUSED"
        screen.blit(title_font.render(speed_text, True, BLACK), (SCREEN_WIDTH - 130, SCREEN_HEIGHT - 70))

        for btn in buttons: btn.draw(screen)
        if all_dead: screen.blit(font.render("ALL AGVS DEAD", True, RED), (300, SCREEN_HEIGHT - 30))

        pygame.display.flip()
        clock.tick(FPS)

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
    
    waiting = True
    while waiting:
        screen.fill(WHITE)
        msg = "Scenario Finished." if dead_agvs < AGV_COUNT else "FAILED (All Dead)."
        res_text = font.render(f"{msg} Time: {sim_time}. Press SPACE.", True, BLACK)
        screen.blit(res_text, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE: waiting = False
    
    pygame.quit()
    return stats

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    print("Starting Simulation...")
    
    stats1 = run_scenario("1. Reactive Fixer (Wait for Break)", agv_strategy_random_safe, fix_strategy_reactive)
    
    if stats1:
        stats2 = run_scenario("2. Proactive Fixer (Predictive)", agv_strategy_smart, fix_strategy_proactive)
        
        if stats2:
            print("\n" + "="*60)
            print("FINAL RESULTS COMPARISON")
            print("="*60)
            print(f"{'Metric':<25} | {'1. Reactive':<20} | {'2. Proactive':<20}")
            print("-" * 75)
            print(f"{'Total Time (ticks)':<25} | {stats1['Total Time']:<20} | {stats2['Total Time']:<20}")
            print(f"{'Total Distance (px)':<25} | {stats1['Total Distance']:<20.2f} | {stats2['Total Distance']:<20.2f}")
            print("-" * 75)
            
            diff = stats1['Total Time'] - stats2['Total Time']
            if diff > 0:
                print(f"CONCLUSION: Proactive Strategy saved {diff} ticks.")
            else:
                print("CONCLUSION: Results are similar.")