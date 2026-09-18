import unittest
from src.decision.decision_engine import DecisionEngine

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.de = DecisionEngine()
        self.healthy_backup = {
            "path_id": "PATH_BACKUP",
            "name": "Backup via SW3",
            "score": 0.18,
            "packet_loss": 0.0,
            "risk": 0.05,
            "interface": "GigabitEthernet0/2"
        }
        self.congested_backup = {
            "path_id": "PATH_BACKUP",
            "name": "Backup via SW3",
            "score": 0.85,
            "packet_loss": 18.0,
            "risk": 0.75,
            "interface": "GigabitEthernet0/2"
        }

    def test_low_risk_no_action(self):
        """Low risk should result in NO_ACTION."""
        pred = {"failure_probability": 0.10, "confidence": 0.95, "predicted_class": "HEALTHY"}
        ttf = {"estimated_ttf_ms": None}
        decision = self.de.evaluate(pred, ttf, "UP", self.healthy_backup)
        self.assertEqual(decision["action"], "NO_ACTION")
        self.assertFalse(decision["should_reroute"])

    def test_medium_risk_increase_monitoring(self):
        """Moderate risk should trigger INCREASE_MONITORING without rerouting."""
        pred = {"failure_probability": 0.55, "confidence": 0.85, "predicted_class": "WARNING"}
        ttf = {"estimated_ttf_ms": 6000}
        decision = self.de.evaluate(pred, ttf, "UP", self.healthy_backup)
        self.assertEqual(decision["action"], "INCREASE_MONITORING")
        self.assertFalse(decision["should_reroute"])

    def test_high_risk_low_confidence_blocks_reroute(self):
        """Confidence gate must BLOCK reroute if confidence < 0.80 (anti-flapping)."""
        pred = {"failure_probability": 0.85, "confidence": 0.65, "predicted_class": "HIGH_RISK"}
        ttf = {"estimated_ttf_ms": 1200}
        decision = self.de.evaluate(pred, ttf, "UP", self.healthy_backup)
        self.assertEqual(decision["action"], "HOLD_UNCONFIRMED")
        self.assertFalse(decision["should_reroute"])

    def test_high_risk_high_confidence_triggers_preemption(self):
        """High risk + high confidence + healthy backup triggers PREEMPTIVE_REROUTE."""
        pred = {"failure_probability": 0.92, "confidence": 0.94, "predicted_class": "HIGH_RISK"}
        ttf = {"estimated_ttf_ms": 850}
        decision = self.de.evaluate(pred, ttf, "UP", self.healthy_backup)
        self.assertEqual(decision["action"], "PREEMPTIVE_REROUTE")
        self.assertTrue(decision["should_reroute"])
        self.assertEqual(decision["target_path_id"], "PATH_BACKUP")

    def test_high_risk_congested_backup_aborts_diversion(self):
        """If candidate backup path is degraded, preemptive switch should be aborted."""
        pred = {"failure_probability": 0.90, "confidence": 0.92, "predicted_class": "HIGH_RISK"}
        ttf = {"estimated_ttf_ms": 900}
        decision = self.de.evaluate(pred, ttf, "UP", self.congested_backup)
        self.assertEqual(decision["action"], "ABORT_CONGESTED_BACKUP")
        self.assertFalse(decision["should_reroute"])

if __name__ == "__main__":
    unittest.main()
