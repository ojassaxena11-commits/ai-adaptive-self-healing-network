import unittest
import numpy as np
import pandas as pd
from src.features.feature_engine import FeatureEngine

class TestFeatureEngine(unittest.TestCase):
    def setUp(self):
        self.fe = FeatureEngine()

    def test_calculate_linear_slope_flat(self):
        """Flat values should produce zero slope."""
        vals = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
        slope = self.fe.calculate_linear_slope(vals)
        self.assertAlmostEqual(slope, 0.0, places=4)

    def test_calculate_linear_slope_positive(self):
        """Strictly increasing values should produce positive slope."""
        vals = np.array([1.0, 3.0, 5.0, 7.0, 9.0])
        slope = self.fe.calculate_linear_slope(vals)
        self.assertAlmostEqual(slope, 2.0, places=4)

    def test_calculate_linear_slope_empty(self):
        """Single or empty values should safely return 0.0."""
        self.assertEqual(self.fe.calculate_linear_slope(np.array([])), 0.0)
        self.assertEqual(self.fe.calculate_linear_slope(np.array([5.0])), 0.0)

    def test_extract_features_structure(self):
        """Verifies feature extraction output keys and bounds."""
        records = [
            {"rtt": 12.0, "jitter": 1.2, "packet_loss": 0.0, "crc_errors": 0, "interface_errors": 0, "interface_flaps": 0, "utilization": 30.0},
            {"rtt": 13.0, "jitter": 1.5, "packet_loss": 0.0, "crc_errors": 1, "interface_errors": 1, "interface_flaps": 0, "utilization": 32.0},
            {"rtt": 15.0, "jitter": 2.2, "packet_loss": 1.0, "crc_errors": 3, "interface_errors": 3, "interface_flaps": 0, "utilization": 35.0},
            {"rtt": 18.0, "jitter": 3.0, "packet_loss": 2.5, "crc_errors": 5, "interface_errors": 5, "interface_flaps": 0, "utilization": 38.0},
            {"rtt": 22.0, "jitter": 4.5, "packet_loss": 4.0, "crc_errors": 8, "interface_errors": 8, "interface_flaps": 1, "utilization": 42.0},
        ]
        df = pd.DataFrame(records)
        feats = self.fe.extract_features(df)

        for col in self.fe.FEATURE_NAMES:
            self.assertIn(col, feats, f"Missing feature: {col}")

        # Check slope is positive during degradation
        self.assertGreater(feats["rtt_slope_5"], 0.0)
        self.assertGreater(feats["jitter_slope_5"], 0.0)
        self.assertGreater(feats["loss_slope_5"], 0.0)
        self.assertGreater(feats["instability_score"], 0.0)
        self.assertLessEqual(feats["instability_score"], 100.0)

if __name__ == "__main__":
    unittest.main()
