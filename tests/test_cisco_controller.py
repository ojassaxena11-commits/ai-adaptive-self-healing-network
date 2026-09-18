import unittest
from src.routing.cisco_controller import CiscoController

class TestCiscoController(unittest.TestCase):
    def setUp(self):
        self.cisco = CiscoController({"mode": "SIMULATION"})
        self.cisco.connect()

    def test_simulated_interface_state(self):
        """Simulated controller should report valid interface status for SW1."""
        status = self.cisco.get_interface_status("SW1")
        self.assertIn("GigabitEthernet0/1", status)
        self.assertTrue(status["GigabitEthernet0/1"]["is_up"])

    def test_dry_run_safety_mode(self):
        """In dry-run mode, change_metric should return True but NOT alter state."""
        self.cisco.set_dry_run(True)
        res = self.cisco.change_metric("SW1", "GigabitEthernet0/1", new_cost=100)
        self.assertTrue(res)
        # Verify internal cost remained 10
        intf = self.cisco.get_interface_status("SW1")["GigabitEthernet0/1"]
        self.assertEqual(intf["cost"], 10)

    def test_live_simulated_metric_change(self):
        """When dry-run is disabled, metric change should modify interface cost."""
        self.cisco.set_dry_run(False)
        self.cisco.change_metric("SW1", "GigabitEthernet0/1", new_cost=100)
        intf = self.cisco.get_interface_status("SW1")["GigabitEthernet0/1"]
        self.assertEqual(intf["cost"], 100)

        # Restore
        self.cisco.restore_metric("SW1", "GigabitEthernet0/1", original_cost=10)
        intf = self.cisco.get_interface_status("SW1")["GigabitEthernet0/1"]
        self.assertEqual(intf["cost"], 10)

if __name__ == "__main__":
    unittest.main()
