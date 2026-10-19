"""
Comprehensive unit and integration test suite for GNS3 Controller integration,
covering all 16 requirements specified in Task 10:
 1. Successful GNS3 connection
 2. Failed GNS3 connection
 3. Retrieving projects
 4. Retrieving nodes and links
 5. Missing projects handling
 6. Missing or stopped devices handling
 7. API timeouts and HTTP error handling
 8. Simulation mode fallback when GNS3 is offline
 9. Failure prediction integration with GNS3 telemetry
 10. Decision-engine behavior
 11. Backup-route validation
 12. Routing operation success
 13. Routing operation failure
 14. Recovery verification
 15. Dashboard labels and rendering
 16. Protection against false success messages
"""

import unittest
from unittest.mock import MagicMock, patch
import requests
import pandas as pd

from src.gns3.gns3_client import GNS3Client
from src.routing.cisco_controller import CiscoController
from src.telemetry.collector import TelemetryCollector
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.feedback.feedback_engine import FeedbackEngine
from src.visualization.topology_visualizer import render_topology_svg


class TestGNS3Integration(unittest.TestCase):

    def setUp(self):
        self.config = {
            "mode": "GNS3",
            "gns3": {
                "host": "localhost",
                "port": 3080,
                "protocol": "http",
                "username": "admin",
                "password": "testpassword",
                "project_name": "AI-Self-Healing-Network",
                "timeout": 2.0
            },
            "network": {
                "source_host": "192.168.1.10",
                "destination_host": "192.168.2.10",
                "primary_path": ["R1", "SW1", "SW2", "R2"],
                "backup_path": ["R1", "SW1", "SW3", "SW2", "R2"],
                "switches": {
                    "SW1": {"management_ip": "10.0.12.2", "primary_interface": "GigabitEthernet0/1", "backup_interface": "GigabitEthernet0/2"},
                    "SW2": {"management_ip": "10.0.24.1"},
                    "SW3": {"management_ip": "10.0.13.2"}
                }
            },
            "decision": {
                "confidence_threshold": 0.80,
                "risk_threshold": 0.75,
                "dry_run": False
            },
            "qos_profiles": {
                "VOIP": {
                    "name": "Voice over IP",
                    "weights": {"latency": 0.30, "packet_loss": 0.35, "utilization": 0.05, "path_risk": 0.20, "hop_count": 0.10}
                },
                "NORMAL_DATA": {
                    "name": "Best-Effort Data (TCP)",
                    "weights": {"latency": 0.20, "packet_loss": 0.15, "utilization": 0.20, "path_risk": 0.20, "hop_count": 0.25}
                }
            }
        }
        self.client = GNS3Client(self.config)

    # --------------------------------------------------------------------------
    # 1. Successful GNS3 connection
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_01_successful_gns3_connection(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"version": "2.2.61", "local": True}

        res = self.client.test_connectivity()
        self.assertEqual(res["status"], GNS3Client.STATUS_CONNECTED)
        self.assertTrue(res["connected"])
        self.assertEqual(res["version"], "2.2.61")
        self.assertIn("Connected to GNS3 successfully", res["message"])

    # --------------------------------------------------------------------------
    # 2. Failed GNS3 connection (ConnectionRefused / Server offline)
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_02_failed_gns3_connection(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection Refused")

        res = self.client.test_connectivity()
        self.assertEqual(res["status"], GNS3Client.STATUS_SERVER_OFFLINE)
        self.assertFalse(res["connected"])
        self.assertIn("Cannot Connect to GNS3: Server is offline", res["message"])
        self.assertTrue(len(res["diagnostics"]) > 0)

    # --------------------------------------------------------------------------
    # 3. Retrieving projects
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_03_retrieving_projects(self, mock_get):
        mock_projects = [
            {"project_id": "proj-1", "name": "AI-Self-Healing-Network", "status": "opened"},
            {"project_id": "proj-2", "name": "Lab-Test-2", "status": "closed"}
        ]
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_projects

        projects = self.client.get_projects()
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["name"], "AI-Self-Healing-Network")
        self.assertEqual(projects[0]["status"], "opened")

    # --------------------------------------------------------------------------
    # 4. Retrieving nodes and links
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_04_retrieving_nodes_and_links(self, mock_get):
        mock_nodes = [
            {"node_id": "n1", "name": "SW1", "node_type": "ethernet_switch", "status": "started"},
            {"node_id": "n2", "name": "SW2", "node_type": "ethernet_switch", "status": "started"}
        ]
        mock_links = [
            {"link_id": "l1", "nodes": [{"node_id": "n1"}, {"node_id": "n2"}], "suspend": False}
        ]

        def get_side_effect(url, **kwargs):
            m = MagicMock()
            m.status_code = 200
            if "/nodes" in url:
                m.json.return_value = mock_nodes
            elif "/links" in url:
                m.json.return_value = mock_links
            return m

        mock_get.side_effect = get_side_effect

        nodes = self.client.get_nodes("test-proj-id")
        links = self.client.get_links("test-proj-id")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]["name"], "SW1")
        self.assertEqual(len(links), 1)
        self.assertFalse(links[0]["suspend"])

    # --------------------------------------------------------------------------
    # 5. Missing projects handling
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_05_missing_projects_handling(self, mock_get):
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.return_value = {"message": "Project not found"}

        proj = self.client.get_project("non-existent-id")
        self.assertIsNone(proj)

        nodes = self.client.get_nodes("non-existent-id")
        self.assertEqual(nodes, [])

        ver = self.client.verify_topology(None)
        self.assertFalse(ver["valid"])
        self.assertIn("No GNS3 project", ver["message"])

    # --------------------------------------------------------------------------
    # 6. Missing or stopped devices handling
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_06_missing_or_stopped_devices(self, mock_get):
        # Only SW1 and SW2 exist; SW3, R1, R2 missing
        mock_nodes = [
            {"node_id": "n1", "name": "SW1", "status": "started"},
            {"node_id": "n2", "name": "SW2", "status": "stopped"}
        ]
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_nodes

        ver = self.client.verify_topology("proj-id")
        self.assertFalse(ver["valid"])
        self.assertIn("SW3", ver["missing_nodes"])
        self.assertIn("R1", ver["missing_nodes"])
        self.assertIn("R2", ver["missing_nodes"])

    # --------------------------------------------------------------------------
    # 7. API timeouts and HTTP error handling
    # --------------------------------------------------------------------------
    @patch("requests.get")
    def test_07_api_timeouts_and_errors(self, mock_get):
        # Timeout
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        res_timeout = self.client.test_connectivity(timeout=1.0)
        self.assertEqual(res_timeout["status"], GNS3Client.STATUS_ERROR)
        self.assertIn("timed out", res_timeout["message"].lower())

        # 401 Unauthorized
        mock_get.side_effect = None
        mock_get.return_value.status_code = 401
        res_auth = self.client.test_connectivity()
        self.assertEqual(res_auth["status"], GNS3Client.STATUS_AUTH_FAILED)
        self.assertIn("Incorrect username or password", res_auth["message"])

    # --------------------------------------------------------------------------
    # 8. Simulation mode fallback when GNS3 is offline
    # --------------------------------------------------------------------------
    def test_08_simulation_mode_when_gns3_offline(self):
        controller = CiscoController(self.config)
        controller.set_mode("SIMULATION")
        self.assertTrue(controller.is_connected())

        collector = TelemetryCollector(self.config, cisco_controller=controller)
        collector.set_mode("SIMULATION")
        step_data = collector.collect_step()

        self.assertIn("primary", step_data)
        self.assertIn("backup", step_data)
        self.assertEqual(step_data["primary"]["telemetry_source"], "SIMULATION")
        self.assertEqual(step_data["primary"]["link_status"], "UP")

    # --------------------------------------------------------------------------
    # 9. Failure prediction integration with GNS3 telemetry
    # --------------------------------------------------------------------------
    def test_09_failure_prediction_integration(self):
        feature_engine = FeatureEngine(self.config)
        predictor = FailurePredictor(config=self.config)
        ttf_predictor = TTFPredictor(config=self.config)

        # Feed healthy sequence
        healthy_df = pd.DataFrame([
            {"rtt": 12.0, "jitter": 1.2, "packet_loss": 0.0, "crc_errors": 0, "interface_errors": 0, "interface_flaps": 0, "utilization": 30.0}
            for _ in range(10)
        ])
        features_healthy = feature_engine.extract_features(healthy_df)
        pred_healthy = predictor.predict(features_healthy)
        self.assertEqual(pred_healthy["predicted_class"], "HEALTHY")
        self.assertLess(pred_healthy["failure_probability"], 0.40)

        # Feed degrading sequence
        degraded_df = pd.DataFrame([
            {"rtt": 45.0 + i*5, "jitter": 12.0 + i*2, "packet_loss": 8.0 + i*2, "crc_errors": 10 + i*5, "interface_errors": i, "interface_flaps": 0, "utilization": 85.0}
            for i in range(10)
        ])
        features_deg = feature_engine.extract_features(degraded_df)
        pred_deg = predictor.predict(features_deg)
        ttf_deg = ttf_predictor.estimate_ttf(features_deg, pred_deg["failure_probability"])

        self.assertIn(pred_deg["predicted_class"], ["WARNING", "HIGH_RISK"])
        self.assertGreaterEqual(pred_deg["failure_probability"], 0.50)
        self.assertIsNotNone(ttf_deg.get("estimated_ttf_ms"))

    # --------------------------------------------------------------------------
    # 10. Decision-engine behavior
    # --------------------------------------------------------------------------
    def test_10_decision_engine_behavior(self):
        engine = DecisionEngine(self.config)
        engine.set_dry_run(False)

        # High risk, high confidence -> evaluate and reroute
        pred_high = {
            "predicted_class": "HIGH_RISK",
            "failure_probability": 0.88,
            "confidence": 0.95,
            "inference_engine": "ML_DECISION_TREE"
        }
        ttf = {"estimated_ttf_ms": 1200.0}
        candidate_backup = {"path_id": "PATH_BACKUP", "risk": 0.05, "packet_loss": 0.0}

        dec = engine.evaluate(
            prediction_result=pred_high,
            ttf_result=ttf,
            primary_link_status="UP",
            best_candidate_path=candidate_backup,
            current_active_path_id="PATH_PRIMARY"
        )
        self.assertTrue(dec["should_reroute"])
        self.assertEqual(dec["action"], "PREEMPTIVE_REROUTE")

    # --------------------------------------------------------------------------
    # 11. Backup-route validation
    # --------------------------------------------------------------------------
    def test_11_backup_route_validation(self):
        path_evaluator = PathEvaluator(self.config)

        # Healthy backup is preferred over degraded primary
        candidates = [
            {"path_id": "PATH_PRIMARY", "name": "Primary (SW1-SW2)", "rtt": 70.0, "packet_loss": 12.0, "utilization": 90.0, "risk": 0.90, "hops": 3},
            {"path_id": "PATH_BACKUP", "name": "Backup (SW1-SW3-SW2)", "rtt": 18.0, "packet_loss": 0.0, "utilization": 25.0, "risk": 0.05, "hops": 4}
        ]
        eval_res = path_evaluator.evaluate_paths(candidates, traffic_class="VOIP")
        self.assertEqual(eval_res["best_path"]["path_id"], "PATH_BACKUP")

        # But if backup path is congested/broken, rerouting is blocked!
        candidates_bad_backup = [
            {"path_id": "PATH_PRIMARY", "name": "Primary (SW1-SW2)", "rtt": 70.0, "packet_loss": 12.0, "utilization": 90.0, "risk": 0.90, "hops": 3},
            {"path_id": "PATH_BACKUP", "name": "Backup (SW1-SW3-SW2)", "rtt": 90.0, "packet_loss": 20.0, "utilization": 95.0, "risk": 0.95, "hops": 4}
        ]
        eval_bad = path_evaluator.evaluate_paths(candidates_bad_backup, traffic_class="VOIP")
        engine = DecisionEngine(self.config)
        dec = engine.evaluate(
            prediction_result={"predicted_class": "HIGH_RISK", "failure_probability": 0.88, "confidence": 0.95},
            ttf_result={"estimated_ttf_ms": 1000.0},
            primary_link_status="UP",
            best_candidate_path=eval_bad["best_path"],
            current_active_path_id="PATH_PRIMARY"
        )
        self.assertFalse(dec["should_reroute"])

    # --------------------------------------------------------------------------
    # 12. Routing operation success
    # --------------------------------------------------------------------------
    def test_12_routing_operation_success(self):
        controller = CiscoController(self.config)
        controller.set_mode("SIMULATION")
        controller.set_dry_run(False)

        success = controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        self.assertTrue(success)
        self.assertEqual(controller.last_action["action"], "CHANGE_METRIC")
        self.assertEqual(controller.last_action["new_cost"], 100)
        self.assertFalse(controller.last_action["dry_run"])

    # --------------------------------------------------------------------------
    # 13. Routing operation failure
    # --------------------------------------------------------------------------
    def test_13_routing_operation_failure(self):
        controller = CiscoController(self.config)
        controller.set_mode("GNS3")
        controller.set_dry_run(False)

        # When GNS3 server is offline, routing operation fails safely
        controller.gns3_client.status = GNS3Client.STATUS_SERVER_OFFLINE
        success = controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        self.assertFalse(success)
        self.assertFalse(controller.last_action["success"])
        self.assertIn("not connected", controller.last_action["output"].lower())

    # --------------------------------------------------------------------------
    # 14. Recovery verification
    # --------------------------------------------------------------------------
    def test_14_recovery_verification(self):
        controller = CiscoController(self.config)
        controller.set_mode("SIMULATION")

        # Baseline: traffic on primary
        ver_base = controller.verify_routing("SW1")
        self.assertTrue(ver_base["verified"])
        self.assertFalse(ver_base["traffic_migrated"])
        self.assertIn("R1 → SW1 → SW2 → R2", ver_base["active_path"])

        # After reroute: metric changed to 100
        controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        ver_rerouted = controller.verify_routing("SW1")
        self.assertTrue(ver_rerouted["verified"])
        self.assertTrue(ver_rerouted["traffic_migrated"])
        self.assertEqual(ver_rerouted["recovery_state"], "RECOVERY_SUCCEEDED")
        self.assertIn("R1 → SW1 → SW3 → SW2 → R2", ver_rerouted["active_path"])

    # --------------------------------------------------------------------------
    # 15. Dashboard labels and rendering
    # --------------------------------------------------------------------------
    def test_15_dashboard_labels_and_rendering(self):
        svg_html = render_topology_svg(
            active_path="R1 → SW1 → SW2 → R2",
            primary_status="UP",
            backup_status="UP",
            primary_cost=10,
            backup_cost=10,
            gns3_connected=True,
            gns3_project_name="AI-Self-Healing-Network"
        )
        # Check node and router labels
        self.assertIn("R1", svg_html)
        self.assertIn("SW1", svg_html)
        self.assertIn("SW2", svg_html)
        self.assertIn("SW3", svg_html)
        self.assertIn("R2", svg_html)
        self.assertIn("Source Gateway", svg_html)
        self.assertIn("Distribution Switch", svg_html)
        self.assertIn("Backup Transit Switch", svg_html)
        self.assertIn("Destination Gateway", svg_html)

        # Check GNS3 live badge
        self.assertIn("GNS3 LIVE", svg_html)
        self.assertIn("AI-Self-Healing-Network", svg_html)

        # Check natural language labels
        self.assertIn("PREDICT NETWORK PROBLEMS", svg_html)
        self.assertIn("CHECK ACTION STATUS", svg_html)
        self.assertIn("PRIMARY ROUTE", svg_html)
        self.assertIn("BACKUP ROUTE", svg_html)

    # --------------------------------------------------------------------------
    # 16. Protection against false success messages
    # --------------------------------------------------------------------------
    def test_16_protection_against_false_success(self):
        controller = CiscoController(self.config)
        controller.set_mode("GNS3")
        controller.gns3_client.status = GNS3Client.STATUS_SERVER_OFFLINE

        # Must not report success when server is offline
        ver = controller.verify_routing("SW1")
        self.assertFalse(ver["verified"])
        self.assertNotEqual(ver["recovery_state"], "RECOVERY_SUCCEEDED")
        self.assertIn("Cannot Connect to GNS3", ver["details"])


if __name__ == "__main__":
    unittest.main()
