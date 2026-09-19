"""
Tests for Cisco Modeling Labs (CML) integration, telemetry normalization,
device command construction, dry-run routing safety, environment switching,
and full self-healing pipeline verification.
"""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.cml.cml_client import CMLClient
from src.telemetry.parser import CiscoOutputParser
from src.telemetry.collector import TelemetryCollector
from src.routing.cisco_controller import CiscoController
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.feedback.feedback_engine import FeedbackEngine


class TestCMLIntegration(unittest.TestCase):

    def setUp(self):
        self.mock_config = {
            "mode": "SIMULATION",
            "cml": {
                "host": "cml.example.local",
                "port": 443,
                "username": "admin",
                "password": "secretpassword",
                "lab_id": "lab-12345",
                "verify_ssl": False
            },
            "network": {
                "primary_path": ["R1", "SW1", "SW2", "R2"],
                "backup_path": ["R1", "SW1", "SW3", "SW2", "R2"],
                "switches": {
                    "SW1": {"management_ip": "10.0.12.2", "primary_intf": "GigabitEthernet0/1", "backup_intf": "GigabitEthernet0/2"},
                    "SW2": {"management_ip": "10.0.24.1"},
                    "SW3": {"management_ip": "10.0.13.2"}
                }
            },
            "decision": {
                "confidence_threshold": 0.80,
                "risk_threshold": 0.75,
                "dry_run": False
            },
            "qos": {
                "profiles": {
                    "VOIP": {"weights": {"rtt": 0.35, "loss": 0.40, "utilization": 0.10, "hops": 0.15}},
                    "NORMAL_DATA": {"weights": {"rtt": 0.25, "loss": 0.25, "utilization": 0.25, "hops": 0.25}}
                }
            }
        }

    def test_cml_client_not_configured_when_missing_credentials(self):
        """CMLClient should accurately reflect NOT CONFIGURED status when host/creds are empty."""
        client = CMLClient(host="", username="", password="")
        self.assertFalse(client.is_configured())
        self.assertEqual(client.status, CMLClient.STATUS_NOT_CONFIGURED)
        res = client.test_connectivity()
        self.assertEqual(res["status"], CMLClient.STATUS_NOT_CONFIGURED)
        self.assertIn("not configured", res["message"].lower())

    def test_cml_client_connected_and_error_handling_mocked(self):
        """CMLClient handles successful REST auth as well as connection errors."""
        client = CMLClient(host="192.168.1.100", username="cml_admin", password="cml_password", lab_id="test-lab")
        self.assertTrue(client.is_configured())

        # Test successful authentication and connectivity
        with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = "token-abcdef123456"

            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "id": "test-lab",
                "state": "STARTED",
                "node_count": 5
            }

            status_res = client.test_connectivity()
            self.assertEqual(status_res["status"], CMLClient.STATUS_CONNECTED)
            self.assertTrue(client.is_authenticated())
            self.assertEqual(client.token, "token-abcdef123456")

        # Test connection failure handling
        with patch("requests.post", side_effect=Exception("Connection refused / Host unreachable")):
            client.token = None
            status_err = client.test_connectivity()
            self.assertEqual(status_err["status"], CMLClient.STATUS_ERROR)
            self.assertIn("Connection refused", status_err["message"])

    def test_cisco_output_parser(self):
        """Verifies parsing of Cisco IOS CLI outputs for interfaces, counters, OSPF, and pings."""
        # 1. Interface Brief
        sample_brief = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/1     10.0.12.2       YES manual up                    up      
GigabitEthernet0/2     10.0.13.1       YES manual administratively down down    
Loopback0              1.1.1.1         YES manual up                    up      
"""
        brief_res = CiscoOutputParser.parse_interface_brief(sample_brief)
        self.assertIn("GigabitEthernet0/1", brief_res)
        self.assertTrue(brief_res["GigabitEthernet0/1"]["is_up"])
        self.assertFalse(brief_res["GigabitEthernet0/2"]["is_up"])

        # 2. Counter Errors
        sample_counters = """
Port      Align-Err    FCS-Err   Xmit-Err    Rcv-Err UnderRun OutDiscards
Gi0/1             0         17          0          0        0           0
Gi0/2             0          0          0          0        0           0
"""
        counter_res = CiscoOutputParser.parse_counters_errors(sample_counters)
        self.assertIn("Gi0/1", counter_res)
        self.assertEqual(counter_res["Gi0/1"]["fcs_crc_err"], 17)

        # 3. Ping parsing
        sample_ping = """
Sending 5, 100-byte ICMP Echos to 192.168.2.1, timeout is 1 seconds:
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 10/14/22 ms
"""
        ping_res = CiscoOutputParser.parse_ping_output(sample_ping)
        self.assertEqual(ping_res["packet_loss"], 0.0)
        self.assertEqual(ping_res["rtt"], 14.0)

        # 4. OSPF Routes
        sample_routes = """
Gateway of last resort is not set
O    192.168.2.0/24 [110/11] via 10.0.12.1, 00:15:23, GigabitEthernet0/1
"""
        routes_res = CiscoOutputParser.parse_ip_route_ospf(sample_routes)
        self.assertEqual(len(routes_res), 1)
        self.assertEqual(routes_res[0]["network"], "192.168.2.0/24")
        self.assertEqual(routes_res[0]["interface"], "GigabitEthernet0/1")

    def test_telemetry_normalization(self):
        """Telemetry collector must supply a standardized schema across both environments."""
        collector = TelemetryCollector(self.mock_config)
        step_data = collector.collect_step()

        self.assertIn("primary", step_data)
        self.assertIn("backup", step_data)

        required_keys = [
            "timestamp", "device", "interface", "path_id", "rtt", "jitter",
            "packet_loss", "crc_errors", "input_errors", "output_errors",
            "utilization", "link_status", "ospf_cost"
        ]

        for p_key in ["primary", "backup"]:
            rec = step_data[p_key]
            for rk in required_keys:
                self.assertIn(rk, rec, f"Normalized telemetry missing required schema key '{rk}' in {p_key}")
            self.assertIsInstance(rec["rtt"], (int, float))
            self.assertIsInstance(rec["packet_loss"], (int, float))
            self.assertIn(rec["link_status"], ["UP", "DOWN"])

    def test_dry_run_safety_mode_vs_live_command_construction(self):
        """Dry-run must formulate commands accurately without executing modifications."""
        controller = CiscoController(self.mock_config)

        # Test Dry Run
        controller.set_dry_run(True)
        res_dry = controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        self.assertTrue(res_dry)
        self.assertIsNotNone(controller.last_action)
        self.assertTrue(controller.last_action["dry_run"])
        self.assertEqual(controller.last_action["commands"], [
            "interface GigabitEthernet0/1",
            "ip ospf cost 100",
            "end"
        ])
        # In dry run, simulated interface cost should remain 10
        self.assertEqual(controller.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["cost"], 10)

        # Test Live (Dry Run Disabled)
        controller.set_dry_run(False)
        res_live = controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        self.assertTrue(res_live)
        self.assertFalse(controller.last_action["dry_run"])
        self.assertEqual(controller.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["cost"], 100)

    def test_shutdown_and_enable_interface_commands(self):
        """Tests controlled failure injection commands: shutdown and no shutdown."""
        controller = CiscoController(self.mock_config)
        controller.set_dry_run(False)

        # Shutdown
        controller.shutdown_interface("SW1", "GigabitEthernet0/1")
        self.assertEqual(controller.last_action["commands"], [
            "interface GigabitEthernet0/1",
            "shutdown",
            "end"
        ])
        self.assertFalse(controller.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["is_up"])

        # Enable (no shutdown)
        controller.enable_interface("SW1", "GigabitEthernet0/1")
        self.assertEqual(controller.last_action["commands"], [
            "interface GigabitEthernet0/1",
            "no shutdown",
            "end"
        ])
        self.assertTrue(controller.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["is_up"])

    def test_environment_switching(self):
        """Switching between SIMULATION and CML maintains object stability and correct mode flags."""
        controller = CiscoController(self.mock_config)
        collector = TelemetryCollector(self.mock_config, cisco_controller=controller)

        self.assertEqual(controller.mode, "SIMULATION")
        self.assertEqual(collector.mode, "SIMULATION")

        # Switch to CML
        controller.mode = "CML"
        collector.mode = "CML"
        self.assertEqual(controller.mode, "CML")
        self.assertEqual(collector.mode, "CML")

        # Telemetry collection still functions seamlessly (with graceful offline fallback)
        step = collector.collect_step()
        self.assertIn("primary", step)
        self.assertIn("backup", step)

        # Switch back to SIMULATION
        controller.mode = "SIMULATION"
        collector.mode = "SIMULATION"
        self.assertEqual(controller.mode, "SIMULATION")
        self.assertTrue(controller.is_connected())

    def test_routing_table_verification(self):
        """Routing verification evaluates whether OSPF has converged traffic to backup transit path."""
        controller = CiscoController(self.mock_config)

        # 1. Baseline - primary cost 10
        v_base = controller.verify_routing("SW1")
        self.assertTrue(v_base["verified"])
        self.assertFalse(v_base["traffic_migrated"])
        self.assertEqual(v_base["active_path"], "R1 → SW1 → SW2 → R2")

        # 2. Cost elevated to 100 - traffic migrated
        controller.change_metric("SW1", "GigabitEthernet0/1", 100)
        v_migrated = controller.verify_routing("SW1")
        self.assertTrue(v_migrated["verified"])
        self.assertTrue(v_migrated["traffic_migrated"])
        self.assertEqual(v_migrated["active_path"], "R1 → SW1 → SW3 → SW2 → R2")

    def test_cml_telemetry_through_ai_pipeline(self):
        """Verify that normalized CML telemetry flows through the entire ML and decision pipeline."""
        collector = TelemetryCollector(self.mock_config)
        fe = FeatureEngine(self.mock_config)
        predictor = FailurePredictor(config=self.mock_config)
        ttf_predictor = TTFPredictor(config=self.mock_config)
        path_eval = PathEvaluator(self.mock_config)
        decision_engine = DecisionEngine(self.mock_config)
        feedback = FeedbackEngine(self.mock_config)

        # Collect 5 consecutive telemetry steps
        p_history = []
        b_history = []
        for _ in range(5):
            step = collector.collect_step()
            p_history.append(step["primary"])
            b_history.append(step["backup"])

        df_p = pd.DataFrame(p_history)
        feats = fe.extract_features(df_p)
        self.assertEqual(len(feats), len(fe.FEATURE_NAMES))

        pred = predictor.predict(feats)
        self.assertIn(pred["predicted_class"], ["HEALTHY", "WARNING", "HIGH_RISK"])

        ttf = ttf_predictor.estimate_ttf(feats, pred["failure_probability"])
        self.assertIn("ttf_range_str", ttf)

        candidates = [
            {"path_id": "PATH_PRIMARY", "name": "Primary", "rtt": p_history[-1]["rtt"], "packet_loss": 0.0, "utilization": 30.0, "risk": pred["failure_probability"], "hops": 3},
            {"path_id": "PATH_BACKUP", "name": "Backup", "rtt": b_history[-1]["rtt"], "packet_loss": 0.0, "utilization": 20.0, "risk": 0.05, "hops": 4}
        ]
        eval_res = path_eval.evaluate_paths(candidates, traffic_class="VOIP")
        self.assertIsNotNone(eval_res["best_path"])

        dec = decision_engine.evaluate(
            prediction_result=pred,
            ttf_result=ttf,
            primary_link_status="UP",
            best_candidate_path=eval_res["best_path"],
            current_active_path_id="PATH_PRIMARY",
            traffic_class="VOIP"
        )
        self.assertIn("action", dec)
        self.assertIn("should_reroute", dec)


if __name__ == "__main__":
    unittest.main()
