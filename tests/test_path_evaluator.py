import unittest
from src.routing.path_evaluator import PathEvaluator

class TestPathEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = PathEvaluator()

    def test_voip_prioritizes_low_jitter_loss(self):
        """VOIP profile should heavily penalize packet loss and latency."""
        paths = [
            {"path_id": "PATH_A", "name": "Path A", "rtt": 12.0, "packet_loss": 5.0, "utilization": 20.0, "risk": 0.1, "hops": 3},
            {"path_id": "PATH_B", "name": "Path B", "rtt": 18.0, "packet_loss": 0.0, "utilization": 50.0, "risk": 0.1, "hops": 4},
        ]
        res = self.evaluator.evaluate_paths(paths, traffic_class="VOIP")
        # Path B with 0% loss should beat Path A despite higher latency and hops
        self.assertEqual(res["best_path"]["path_id"], "PATH_B")

    def test_video_prioritizes_low_utilization(self):
        """Video profile should prioritize lower link utilization/bandwidth headroom."""
        paths = [
            {"path_id": "PATH_A", "name": "Path A", "rtt": 15.0, "packet_loss": 0.0, "utilization": 90.0, "risk": 0.05, "hops": 3},
            {"path_id": "PATH_B", "name": "Path B", "rtt": 20.0, "packet_loss": 0.0, "utilization": 20.0, "risk": 0.05, "hops": 4},
        ]
        res = self.evaluator.evaluate_paths(paths, traffic_class="VIDEO")
        self.assertEqual(res["best_path"]["path_id"], "PATH_B")

if __name__ == "__main__":
    unittest.main()
