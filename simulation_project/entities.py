"""
Entities flowing through the system.
"""

class Tray:
    def __init__(self, id, creation_time):
        self.id = id
        self.creation_time = creation_time
        # Times for tracking/stats
        self.planted_time = None
        self.grown_time = None
        self.harvest_completed_time = None
        
        # State
        self.is_planted = False
        self.is_grown = False
        
    def __repr__(self):
        return f"Tray_{self.id}"
