import unittest
import time
from src.feedback.feedback_engine import FeedbackEngine

class TestFeedbackEngine(unittest.TestCase):
    def setUp(self):
        self.fb = FeedbackEngine()

    def test_classification_true_positive(self):
        """Predicted high risk + actual failure occurred = TRUE_POSITIVE."""
        res = self.fb.evaluate_cycle(
            scenario="TEST",
            predicted_risk=0.88,
            actual_failure_occurred=True,
            rerouted=True,
            current_loss=0.0,
            current_rtt=18.0
        )
        self.assertEqual(res["feedback_category"], "TRUE_POSITIVE")
        self.assertEqual(res["recovery_status"], "RECOVERY_SUCCESS")

    def test_classification_false_positive(self):
        """Predicted high risk + no failure occurred = FALSE_POSITIVE."""
        res = self.fb.evaluate_cycle(
            scenario="TEST",
            predicted_risk=0.85,
            actual_failure_occurred=False,
            rerouted=False,
            current_loss=0.0,
            current_rtt=12.0
        )
        self.assertEqual(res["feedback_category"], "FALSE_POSITIVE")

    def test_hysteresis_flapping_prevention(self):
        """Link must remain stable across duration before restoring metric."""
        # Initial check
        h1 = self.fb.evaluate_restoration_hysteresis(primary_link_up=True, primary_failure_prob=0.05)
        # Should not immediately restore on sample 1
        self.assertFalse(h1["can_restore"])

        # Feed 9 more healthy samples
        for _ in range(9):
            h = self.fb.evaluate_restoration_hysteresis(primary_link_up=True, primary_failure_prob=0.05)

        # After 10 consecutive healthy samples, restoration should be approved
        self.assertTrue(h["can_restore"])

if __name__ == "__main__":
    unittest.main()
