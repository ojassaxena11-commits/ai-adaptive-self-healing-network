import unittest
import pandas as pd
from src.telemetry.simulator import NetworkSimulator
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.routing.path_evaluator import PathEvaluator

class TestScenarioSimulation(unittest.TestCase):
    def setUp(self):
        self.sim = NetworkSimulator()
        self.fe = FeatureEngine()
        self.predictor = FailurePredictor()
        self.path_eval = PathEvaluator()

    def test_step_once_progression(self):
        """Repeated steps without resetting scenario must advance step_count 1, 2, 3, 4, 5..."""
        self.sim.set_scenario(3)
        self.assertEqual(self.sim.step_count, 0)

        steps = []
        for expected_step in range(1, 6):
            data = self.sim.generate_telemetry_step()
            self.assertEqual(self.sim.step_count, expected_step)
            steps.append(data)

        # Verify time-series progression: degradation in Scenario 3 should cause metrics to change
        step1_rtt = steps[0]["primary"]["rtt"]
        step5_rtt = steps[4]["primary"]["rtt"]
        self.assertNotEqual(step1_rtt, step5_rtt)

    def test_scenario_switching(self):
        """Switching scenarios resets step_count to 0 and accumulated state, but subsequent steps advance."""
        self.sim.set_scenario(4)
        for _ in range(10):
            self.sim.generate_telemetry_step()
        self.assertEqual(self.sim.step_count, 10)
        self.assertGreater(self.sim.primary_crc_total, 0)

        # Switch scenario to 1
        self.sim.set_scenario(1)
        self.assertEqual(self.sim.scenario, 1)
        self.assertEqual(self.sim.step_count, 0)
        self.assertEqual(self.sim.primary_crc_total, 0)
        self.assertTrue(self.sim.primary_link_up)
        self.assertTrue(self.sim.backup_link_up)

        # Generate first step of new scenario
        step1 = self.sim.generate_telemetry_step()
        self.assertEqual(self.sim.step_count, 1)
        self.assertEqual(step1["primary"]["link_status"], "UP")

        # Advance next step without resetting
        step2 = self.sim.generate_telemetry_step()
        self.assertEqual(self.sim.step_count, 2)

    def test_backup_telemetry_propagation(self):
        """Simulator must generate and propagate telemetry for both primary and backup links."""
        self.sim.set_scenario(1)
        step_data = self.sim.generate_telemetry_step()

        self.assertIn("primary", step_data)
        self.assertIn("backup", step_data)

        p = step_data["primary"]
        b = step_data["backup"]

        # Check required fields
        required_keys = [
            "timestamp", "device", "interface", "path_id", "rtt", "jitter",
            "packet_loss", "crc_errors", "interface_errors", "interface_flaps",
            "utilization", "link_status", "ospf_cost", "telemetry_source"
        ]
        for key in required_keys:
            self.assertIn(key, p)
            self.assertIn(key, b)

        self.assertEqual(p["path_id"], "PATH_PRIMARY")
        self.assertEqual(b["path_id"], "PATH_BACKUP")
        self.assertEqual(p["interface"], "GigabitEthernet0/1")
        self.assertEqual(b["interface"], "GigabitEthernet0/2")

    def test_scenario_8_backup_degradation(self):
        """Scenario 8: Primary remains normal while backup progressively degrades, worsening QoS score."""
        self.sim.set_scenario(8)
        backup_history = []
        primary_history = []

        for _ in range(1, 11):
            data = self.sim.generate_telemetry_step()
            primary_history.append(data["primary"])
            backup_history.append(data["backup"])

        # Primary link should remain healthy
        for p in primary_history:
            self.assertEqual(p["link_status"], "UP")
            self.assertEqual(p["packet_loss"], 0.0)
            self.assertLess(p["rtt"], 20.0)

        # Backup link must progressively worsen
        b_first = backup_history[0]   # Step 1
        b_last = backup_history[-1]   # Step 10

        self.assertGreater(b_last["rtt"], b_first["rtt"])
        self.assertGreater(b_last["jitter"], b_first["jitter"])
        self.assertGreater(b_last["packet_loss"], b_first["packet_loss"])
        self.assertGreater(b_last["crc_errors"], b_first["crc_errors"])
        self.assertGreater(b_last["utilization"], b_first["utilization"])

        # Candidate QoS evaluation with degraded backup
        b_df = pd.DataFrame(backup_history)
        b_feats = self.fe.extract_features(b_df)
        b_pred = self.predictor.predict(b_feats)

        candidates = [
            {
                "path_id": "PATH_PRIMARY",
                "name": "R1 → SW1 → SW2 → R2",
                "rtt": primary_history[-1]["rtt"],
                "packet_loss": primary_history[-1]["packet_loss"],
                "utilization": primary_history[-1]["utilization"],
                "risk": 0.05,
                "hops": 3,
                "interface": "GigabitEthernet0/1"
            },
            {
                "path_id": "PATH_BACKUP",
                "name": "R1 → SW1 → SW3 → SW2 → R2",
                "rtt": b_last["rtt"],
                "packet_loss": b_last["packet_loss"],
                "utilization": b_last["utilization"],
                "risk": b_pred["failure_probability"],
                "hops": 4,
                "interface": "GigabitEthernet0/2"
            }
        ]
        eval_result = self.path_eval.evaluate_paths(candidates, traffic_class="VOIP")

        # In Scenario 8, backup penalty score must be significantly worse than primary
        ranked = eval_result["ranked_paths"]
        self.assertEqual(ranked[0]["path_id"], "PATH_PRIMARY")
        self.assertEqual(ranked[1]["path_id"], "PATH_BACKUP")
        self.assertGreater(ranked[1]["score"], ranked[0]["score"])

    def test_reset_behavior(self):
        """Reset must restore Scenario 1, step_count=0, links UP, costs 10, clean accumulators."""
        # Drive simulator into modified/degraded state
        self.sim.set_scenario(4)
        for _ in range(20):
            self.sim.generate_telemetry_step()
        self.sim.set_primary_cost(100)
        self.sim.set_backup_cost(50)

        # Call reset
        self.sim.reset()

        self.assertEqual(self.sim.scenario, 1)
        self.assertEqual(self.sim.step_count, 0)
        self.assertTrue(self.sim.primary_link_up)
        self.assertTrue(self.sim.backup_link_up)
        self.assertEqual(self.sim.primary_ospf_cost, 10)
        self.assertEqual(self.sim.backup_ospf_cost, 10)
        self.assertEqual(self.sim.primary_crc_total, 0)
        self.assertEqual(self.sim.primary_err_total, 0)
        self.assertEqual(self.sim.primary_flaps, 0)
        self.assertEqual(self.sim.backup_crc_total, 0)
        self.assertEqual(self.sim.backup_err_total, 0)
        self.assertEqual(self.sim.backup_flaps, 0)

if __name__ == "__main__":
    unittest.main()
