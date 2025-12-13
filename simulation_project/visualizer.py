"""
Pygame-based Visualizer for the simulation.
"""
import pygame
import sys
import time
from .config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    PLANTING_POS, SHELF_POS, HARVEST_POS, FPS
)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 0, 200)
GRAY = (200, 200, 200)
RED = (200, 0, 0)

class Visualizer:
    def __init__(self, sim_instance, scenario_name="Simulation"):
        self.sim = sim_instance
        self.env = sim_instance.env
        self.resources = sim_instance.resources
        self.scenario_name = scenario_name
        
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Vertical Farm Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.score_font = pygame.font.SysFont("Arial", 20, bold=True)
        
        self.running = True
    
    def show_transition_screen(self, message, duration=2.0):
        """Show a transition screen with a message."""
        start_time = time.time()
        while time.time() - start_time < duration:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return
            self.screen.fill(BLACK)
            text = self.title_font.render(message, True, WHITE)
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(text, text_rect)
            pygame.display.flip()
            time.sleep(0.016)

    def process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    pygame.quit()
                    sys.exit()

    def update(self):
        if not self.running:
            return

        self.process_events()
        
        # Clear
        self.screen.fill(WHITE)
        
        # Draw Scenery
        self.draw_station("Planting", PLANTING_POS, GREEN)
        self.draw_station("Shelf", SHELF_POS, GRAY, size=80)
        self.draw_station("Harvest", HARVEST_POS, RED)
        
        # Draw Trays on Shelf (Simplified count)
        shelf_count = self.resources.shelves.level
        text = self.font.render(f"Stored: {shelf_count}", True, BLACK)
        self.screen.blit(text, (SHELF_POS[0] - 20, SHELF_POS[1] + 50))
        
        # Draw AGVs
        for agv in self.resources.agvs:
            self.draw_agv(agv)
            
        # Draw Time
        time_text = self.font.render(f"Time: {self.env.now:.1f}s", True, BLACK)
        self.screen.blit(time_text, (10, 10))
        
        # Draw Scenario Name
        scenario_text = self.title_font.render(self.scenario_name, True, BLUE)
        self.screen.blit(scenario_text, (SCREEN_WIDTH - 300, 10))
        
        # Draw Score
        score_text = self.score_font.render(f"Completed Trays: {self.sim.trays_completed}", True, GREEN)
        self.screen.blit(score_text, (10, 40))

        pygame.display.flip()
        
    def draw_end_screen(self):
        # Just keep drawing the last state but check for quit
        self.update() 

    def draw_station(self, name, pos, color, size=40):
        rect = pygame.Rect(pos[0] - size//2, pos[1] - size//2, size, size)
        pygame.draw.rect(self.screen, color, rect)
        text = self.font.render(name, True, BLACK)
        self.screen.blit(text, (pos[0] - size//2, pos[1] - 20))

    def draw_agv(self, agv):
        # Interpolate Position
        current_x, current_y = agv.pos
        
        if agv.state.startswith("MOVING"):
            elapsed = self.env.now - agv.move_start_time
            if elapsed < agv.move_duration and agv.move_duration > 0:
                progress = elapsed / agv.move_duration
                start_x, start_y = agv.pos
                target_x, target_y = agv.target_pos
                current_x = start_x + (target_x - start_x) * progress
                current_y = start_y + (target_y - start_y) * progress
        
        # Draw Robot Body
        rect = pygame.Rect(current_x - 10, current_y - 10, 20, 20)
        pygame.draw.rect(self.screen, BLUE, rect)
        
        # Label ID
        text = self.font.render(str(agv.id), True, WHITE)
        self.screen.blit(text, (current_x - 5, current_y - 8))
        
        # Visual State
        if agv.carrying_tray:
            # Draw Tray on top
            pygame.draw.circle(self.screen, GREEN, (int(current_x), int(current_y)), 5)
