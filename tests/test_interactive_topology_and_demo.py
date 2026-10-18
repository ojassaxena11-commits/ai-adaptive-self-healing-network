"""
Tests for Interactive Network Topology visualization, multi-step scenario progression,
reset behavior, route highlighting, congested backup rejection, successful simulated rerouting,
dry-run safety, and failure recovery states.
"""

import unittest
import pandas as pd

from src.visualization.topology_visualizer import render_topology_svg
from src.telemetry.simulator import NetworkSimulator
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.routing.cisco_controller import CiscoController
from src.feedback.feedback_engine import FeedbackEngine


class TestInteractiveTopologyAndDemo(unittest.TestCase):

    def setUp(self):
        self.config = {
            "mode": "SIMULATION",
            "decision": {"dry_run": True, "risk_threshold": 0.75, "confidence_threshold": 0.80},
            "network": {
                "primary_path": ["R1", "SW1", "SW2", "R2"],
                "backup_path": ["R1", "SW1", "SW3", "SW2", "R2"]
            },
            "qos_profiles": {
                "VOIP": {"weights": {"latency": 0.30, "packet_loss": 0.35, "utilization": 0.05, "path_risk": 0.20, "hop_count": 0.10}},
                "NORMAL_DATA": {"weights": {"latency": 0.20, "packet_loss": 0.15, "utilization": 0.20, "path_risk": 0.20, "hop_count": 0.25}}
            }
        }
        self.sim = NetworkSimulator(self.config)
        self.fe = FeatureEngine(self.config)
        self.predictor = FailurePredictor(config=self.config)
        self.ttf_pred = TTFPredictor(config=self.config)
        self.path_eval = PathEvaluator(self.config)
        self.decision_engine = DecisionEngine(self.config)
        self.cisco = CiscoController(self.config)
        self.feedback = FeedbackEngine(self.config)

    def test_topology_svg_primary_route_highlighting(self):
        """Topology SVG correctly renders nodes and highlights the active Primary route."""
        svg_html = render_topology_svg(
            active_path="R1 → SW1 → SW2 → R2",
            primary_status="UP",
            backup_status="UP",
            primary_cost=10,
            backup_cost=10
        )
        # Verify nodes are present
        for node in ["R1", "SW1", "SW2", "SW3", "R2"]:
            self.assertIn(node, svg_html, f"Node {node} missing from topology visualizer")

        # Verify primary path styling
        self.assertIn("ACTIVE PATH: PRIMARY ROUTE", svg_html)
        self.assertIn("Cost 10 | ACTIVE", svg_html)
        self.assertIn("10.0.12.1", svg_html)
        self.assertIn("10.0.24.2", svg_html)

    def test_topology_svg_backup_route_highlighting(self):
        """Topology SVG shifts active styling and directional animation to Backup path upon reroute."""
        svg_html = render_topology_svg(
            active_path="R1 → SW1 → SW3 → SW2 → R2",
            primary_status="UP",
            backup_status="UP",
            primary_cost=100,
            backup_cost=10
        )
        self.assertIn("PREEMPTIVE PATH: REDUNDANT TRANSIT", svg_html)
        self.assertIn("Cost 100", svg_html)
        self.assertIn("Cost 40 Total | ACTIVE", svg_html)

    def test_topology_svg_congested_and_failed_states(self):
        """Topology SVG visually reflects warning, congestion, and failure states."""
        # Failure state
        svg_failed = render_topology_svg(
            active_path="R1 → SW1 → SW3 → SW2 → R2",
            primary_status="DOWN",
            primary_cost=100
        )
        self.assertIn("FAILED", svg_failed)

        # Congested state
        svg_congested = render_topology_svg(
            active_path="R1 → SW1 → SW2 → R2",
            primary_status="UP",
            ai_prediction={"failure_probability": 0.88, "predicted_class": "HIGH_RISK"}
        )
        self.assertIn("CONGESTED", svg_congested)

    def test_scenario_progression_and_reset(self):
        """Step-once actions advance scenario without reset; explicit reset restores baseline."""
        self.sim.set_scenario(4)
        self.assertEqual(self.sim.step_count, 0)

        # Advance 5 steps sequentially
        for step in range(1, 6):
            rec = self.sim.generate_telemetry_step()
            self.assertEqual(self.sim.step_count, step)
            self.assertIn("primary", rec)

        # Reset returns to Scenario 1, step 0, baseline costs
        self.sim.reset()
        self.assertEqual(self.sim.scenario, 1)
        self.assertEqual(self.sim.step_count, 0)
        self.assertEqual(self.sim.primary_ospf_cost, 10)
        self.assertEqual(self.sim.backup_ospf_cost, 10)
        self.assertTrue(self.sim.primary_link_up)

    def test_dry_run_safety_guarantees(self):
        """Dry-run safety mode ensures no actual state mutation occurs."""
        self.cisco.set_dry_run(True)
        self.decision_engine.set_dry_run(True)

        res = self.cisco.change_metric("SW1", "GigabitEthernet0/1", new_cost=100)
        self.assertTrue(res)
        self.assertTrue(self.cisco.last_action["dry_run"])
        # In dry run, internal cost remains 10
        self.assertEqual(self.cisco.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["cost"], 10)

    def test_congested_backup_rejection(self):
        """If backup path is degraded or congested, AI decision engine MUST abort rerouting."""
        # Scenario 5: Primary degraded, but backup is congested (Loss > 5.0% or risk >= 0.70)
        high_risk_pred = {
            "failure_probability": 0.88,
            "confidence": 0.90,
            "predicted_class": "HIGH_RISK"
        }
        ttf = {"estimated_ttf_ms": 1100, "ttf_range_str": "1.1s"}
        congested_candidate = {
            "path_id": "PATH_BACKUP",
            "name": "Backup via SW3",
            "packet_loss": 8.5,  # Congested!
            "rtt": 72.0,
            "risk": 0.75,
            "score": 0.92
        }

        decision = self.decision_engine.evaluate(
            prediction_result=high_risk_pred,
            ttf_result=ttf,
            primary_link_status="UP",
            best_candidate_path=congested_candidate,
            current_active_path_id="PATH_PRIMARY"
        )

        self.assertEqual(decision["action"], "ABORT_CONGESTED_BACKUP")
        self.assertFalse(decision["should_reroute"])
        self.assertEqual(decision["target_path_id"], "PATH_PRIMARY")
        self.assertIn("rejected", decision["reason"].lower())

    def test_successful_simulated_rerouting_flow(self):
        """High risk + healthy backup successfully triggers PREEMPTIVE_REROUTE and converges."""
        self.cisco.set_dry_run(False)
        self.decision_engine.set_dry_run(False)

        high_risk_pred = {
            "failure_probability": 0.89,
            "confidence": 0.92,
            "predicted_class": "HIGH_RISK"
        }
        ttf = {"estimated_ttf_ms": 950, "ttf_range_str": "950ms"}
        healthy_backup = {
            "path_id": "PATH_BACKUP",
            "name": "Backup via SW3",
            "packet_loss": 0.0,
            "rtt": 18.0,
            "risk": 0.05,
            "score": 0.15
        }

        decision = self.decision_engine.evaluate(
            prediction_result=high_risk_pred,
            ttf_result=ttf,
            primary_link_status="UP",
            best_candidate_path=healthy_backup,
            current_active_path_id="PATH_PRIMARY"
        )

        self.assertEqual(decision["action"], "PREEMPTIVE_REROUTE")
        self.assertTrue(decision["should_reroute"])

        # Execute metric reconfiguration
        self.cisco.change_metric("SW1", "GigabitEthernet0/1", 100)
        self.sim.set_primary_cost(100)

        # Verify routing table reflects traffic migration to SW3
        ver = self.cisco.verify_routing("SW1")
        self.assertTrue(ver["verified"])
        self.assertTrue(ver["traffic_migrated"])
        self.assertIn("SW3", ver["active_path"])

    def test_failure_and_recovery_states(self):
        """Tests shutdown failure injection followed by recovery and anti-flapping hysteresis."""
        self.cisco.set_dry_run(False)

        # 1. Shutdown Primary Link
        self.cisco.shutdown_interface("SW1", "GigabitEthernet0/1")
        self.assertFalse(self.cisco.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["is_up"])

        # 2. Re-enable Primary Link
        self.cisco.enable_interface("SW1", "GigabitEthernet0/1")
        self.assertTrue(self.cisco.simulated_interfaces["SW1"]["GigabitEthernet0/1"]["is_up"])

        # 3. Hysteresis observation: Requires consecutive healthy samples before restoration
        hyst = self.feedback.evaluate_restoration_hysteresis(primary_link_up=True, primary_failure_prob=0.05)
        # First sample should be in observation timer
        self.assertFalse(hyst["can_restore"])
        self.assertIn("Stabilizing", hyst["reason"])


if __name__ == "__main__":
    unittest.main()
