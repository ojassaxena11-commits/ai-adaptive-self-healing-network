import argparse
import time
import sys
from typing import Dict, Any

from src.utils.logger import logger
from src.utils.config_loader import load_config
from src.telemetry.collector import TelemetryCollector
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.routing.cisco_controller import CiscoController
from src.feedback.feedback_engine import FeedbackEngine

def main():
    parser = argparse.ArgumentParser(description="AI-Driven Adaptive Self-Healing Network Controller")
    parser.add_argument("--mode", choices=["simulation", "cml"], default=None, help="Operating Mode: simulation or cml")
    parser.add_argument("--scenario", type=int, default=1, choices=range(1, 9), help="Simulation Scenario (1-8)")
    parser.add_argument("--traffic-class", choices=["voip", "video", "data"], default="data", help="Application traffic class")
    parser.add_argument("--dry-run", action="store_true", help="Enable dry-run safety mode (no config mutations)")
    parser.add_argument("--steps", type=int, default=30, help="Number of telemetry cycles to execute")
    parser.add_argument("--verify-connectivity", action="store_true", help="Test connection to CML / Cisco devices and exit")
    args = parser.parse_args()

    config = load_config()

    if args.mode:
        config["mode"] = args.mode.upper()
    if args.dry_run:
        config["decision"]["dry_run"] = True

    mode = config.get("mode", "SIMULATION").upper()
    traffic_class_map = {"voip": "VOIP", "video": "VIDEO", "data": "NORMAL_DATA"}
    traffic_class = traffic_class_map.get(args.traffic_class.lower(), "NORMAL_DATA")

    logger.info("=================================================================")
    logger.info(f"AI-DRIVEN ADAPTIVE SELF-HEALING NETWORK CONTROLLER")
    logger.info(f"OPERATIONAL MODE: {mode} | TRAFFIC CLASS: {traffic_class} | DRY_RUN: {config['decision']['dry_run']}")
    logger.info("=================================================================")

    # Initialize Automation & Controller
    cisco_controller = CiscoController(config)
    cisco_controller.connect()

    if args.verify_connectivity:
        logger.info(f"Connectivity check complete for {mode} mode.")
        sys.exit(0)

    # Initialize System Pipeline
    collector = TelemetryCollector(config, cisco_controller=cisco_controller)
    collector.set_scenario(args.scenario)

    feature_engine = FeatureEngine(config)
    predictor = FailurePredictor(config=config)
    ttf_predictor = TTFPredictor(config=config)
    path_evaluator = PathEvaluator(config)
    decision_engine = DecisionEngine(config)
    feedback_engine = FeedbackEngine(config)

    active_path_id = "PATH_PRIMARY"
    primary_cost = 10

    logger.info(f"Starting continuous monitoring loop (Scenario {args.scenario}). Press Ctrl+C to stop.\n")

    try:
        for step in range(1, args.steps + 1):
            # 1. Collect Telemetry
            telemetry = collector.collect_step()
            p_data = telemetry["primary"]
            b_data = telemetry["backup"]

            # 2. Extract Features
            hist_df = collector.get_recent_history(path_id="PATH_PRIMARY", n_samples=20)
            features = feature_engine.extract_features(hist_df)

            # 3. Predict Failure & TTF
            prediction = predictor.predict(features)
            ttf = ttf_predictor.estimate_ttf(features, prediction["failure_probability"])

            # 4. Evaluate Paths with QoS
            candidate_paths = [
                {
                    "path_id": "PATH_PRIMARY",
                    "name": "Primary (SW1-SW2)",
                    "rtt": p_data["rtt"],
                    "packet_loss": p_data["packet_loss"],
                    "utilization": p_data["utilization"],
                    "risk": prediction["failure_probability"],
                    "hops": 3,
                    "interface": "GigabitEthernet0/1"
                },
                {
                    "path_id": "PATH_BACKUP",
                    "name": "Backup (SW1-SW3-SW2)",
                    "rtt": b_data["rtt"],
                    "packet_loss": b_data["packet_loss"],
                    "utilization": b_data["utilization"],
                    "risk": 0.05,
                    "hops": 4,
                    "interface": "GigabitEthernet0/2"
                }
            ]
            path_eval = path_evaluator.evaluate_paths(candidate_paths, traffic_class=traffic_class)
            best_path = path_eval["best_path"]

            # 5. Make Decision
            decision = decision_engine.evaluate(
                prediction_result=prediction,
                ttf_result=ttf,
                primary_link_status=p_data["link_status"],
                best_candidate_path=best_path,
                current_active_path_id=active_path_id,
                traffic_class=traffic_class
            )

            # 6. Execute Routing Action if needed
            if decision["should_reroute"] and active_path_id == "PATH_PRIMARY":
                logger.warning(f"[DECISION ENGINE] PREEMPTIVE REROUTE TRIGGERED: {decision['reason']}")
                success = cisco_controller.change_metric("SW1", "GigabitEthernet0/1", new_cost=100)
                if success:
                    active_path_id = "PATH_BACKUP"
                    primary_cost = 100
                    feedback_engine.record_reroute(decision)

            # 7. Check Anti-Flapping Route Restoration Hysteresis if on backup
            if active_path_id == "PATH_BACKUP":
                hyst = feedback_engine.evaluate_restoration_hysteresis(
                    primary_link_up=(p_data["link_status"] == "UP"),
                    primary_failure_prob=prediction["failure_probability"]
                )
                if hyst["can_restore"]:
                    logger.info(f"[HYSTERESIS] Restoring primary route preference: {hyst['reason']}")
                    cisco_controller.restore_metric("SW1", "GigabitEthernet0/1", original_cost=10)
                    active_path_id = "PATH_PRIMARY"
                    primary_cost = 10

            # 8. Record Feedback & Log Step
            fb = feedback_engine.evaluate_cycle(
                scenario=f"SCENARIO_{args.scenario}",
                predicted_risk=prediction["failure_probability"],
                actual_failure_occurred=(p_data["link_status"] == "DOWN"),
                rerouted=(active_path_id == "PATH_BACKUP"),
                current_loss=p_data["packet_loss"] if active_path_id == "PATH_PRIMARY" else b_data["packet_loss"],
                current_rtt=p_data["rtt"] if active_path_id == "PATH_PRIMARY" else b_data["rtt"],
                selected_path=active_path_id
            )

            # Rich Console Output
            risk_pct = prediction["failure_probability"] * 100
            conf_pct = prediction["confidence"] * 100
            ttf_str = ttf.get("ttf_range_str", "N/A")
            logger.info(
                f"Step {step:02d} | Route: {active_path_id:<12} (Cost: {primary_cost}) | "
                f"RTT: {p_data['rtt']:5.1f}ms | Loss: {p_data['packet_loss']:4.1f}% | "
                f"Risk: {risk_pct:5.1f}% | Conf: {conf_pct:5.1f}% | TTF: {ttf_str} | Action: {decision['action']}"
            )

            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Monitoring terminated by operator.")

    logger.info("Execution complete.")

if __name__ == "__main__":
    main()
