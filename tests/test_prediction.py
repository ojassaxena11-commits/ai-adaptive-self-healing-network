import unittest
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor

class TestPrediction(unittest.TestCase):
    def setUp(self):
        self.predictor = FailurePredictor()
        self.ttf_predictor = TTFPredictor()

    def test_healthy_prediction(self):
        """Healthy baseline features should yield LOW failure probability."""
        healthy_features = {
            "rtt_current": 11.5, "rtt_mean_5": 11.2, "rtt_std_5": 0.3, "rtt_slope_5": 0.02,
            "jitter_current": 1.2, "jitter_mean_5": 1.1, "jitter_std_5": 0.1, "jitter_slope_5": 0.01,
            "loss_current": 0.0, "loss_mean_5": 0.0, "loss_slope_5": 0.0,
            "crc_current": 0, "crc_growth_5": 0.0, "err_current": 0, "err_growth_5": 0.0,
            "flaps_current": 0, "util_current": 30.0, "util_mean_5": 29.0, "util_slope_5": 0.1,
            "instability_score": 2.5
        }
        res = self.predictor.predict(healthy_features)
        self.assertEqual(res["predicted_class"], "HEALTHY")
        self.assertLess(res["failure_probability"], 0.30)
        self.assertGreaterEqual(res["confidence"], 0.70)

        # TTF should be non-critical / stable
        ttf_res = self.ttf_predictor.estimate_ttf(healthy_features, res["failure_probability"])
        self.assertFalse(ttf_res["is_critical"])

    def test_high_risk_degradation_prediction(self):
        """Severely degrading link features must trigger HIGH_RISK prediction."""
        degraded_features = {
            "rtt_current": 45.0, "rtt_mean_5": 38.0, "rtt_std_5": 6.2, "rtt_slope_5": 5.4,
            "jitter_current": 14.0, "jitter_mean_5": 11.0, "jitter_std_5": 2.8, "jitter_slope_5": 3.2,
            "loss_current": 9.5, "loss_mean_5": 7.0, "loss_slope_5": 2.1,
            "crc_current": 25, "crc_growth_5": 12.0, "err_current": 30, "err_growth_5": 15.0,
            "flaps_current": 1, "util_current": 75.0, "util_mean_5": 68.0, "util_slope_5": 4.0,
            "instability_score": 82.5
        }
        res = self.predictor.predict(degraded_features)
        self.assertEqual(res["predicted_class"], "HIGH_RISK")
        self.assertGreaterEqual(res["failure_probability"], 0.75)
        self.assertGreaterEqual(res["confidence"], 0.80)

        # Check explainable contributing indicators
        self.assertGreater(len(res["contributing_indicators"]), 0)

        # TTF should estimate critical window [300, 5000] ms
        ttf_res = self.ttf_predictor.estimate_ttf(degraded_features, res["failure_probability"])
        self.assertTrue(ttf_res["is_critical"])
        self.assertIsNotNone(ttf_res["estimated_ttf_ms"])
        self.assertLess(ttf_res["estimated_ttf_ms"], 5000)

if __name__ == "__main__":
    unittest.main()
