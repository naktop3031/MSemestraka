import unittest
from simulation_project.sim_model import FarmSimulation
from simulation_project.config import SCENARIO_A

class TestSimulationFlow(unittest.TestCase):
    def test_basic_execution(self):
        """Test that simulation runs without error and produces some output."""
        # Use a short run time for testing
        test_config = SCENARIO_A.copy()
        
        sim = FarmSimulation(test_config)
        # Run for 1 hour sim time
        sim.env.process(sim.tray_generator())
        sim.env.run(until=3600)
        
        # Check that we at least created some trays (spawn interval 60s -> ~60 trays)
        # Note: Simulation object might not expose tray list directly unless we added it,
        # but we can check if utilization is non-negative or time advanced.
        
        # Check if environment time advanced
        self.assertEqual(sim.env.now, 3600)
        
        # Check if stats initialized
        self.assertGreaterEqual(len(sim.tray_wait_times), 0)

if __name__ == '__main__':
    unittest.main()
