import os
import csv
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.utils.logger import logger

class FeedbackEngine:
    """
    Feedback Evaluation & Anti-Flapping Route Restoration Hysteresis Engine.
    Tracks ML accuracy outcomes (TP, FP, TN, FN), calculates proactive lead time,
    evaluates recovery success (RECOVERY_SUCCESS vs RECOVERY_FAILURE),
    and enforces strict stability timers before reverting traffic to the primary path.
    """

    EVENT_LOG_HEADER = [
        "timestamp", "scenario", "device", "interface", "prediction",
        "failure_probability", "confidence", "estimated_ttf", "selected_path",
        "action", "actual_failure", "recovery_success", "lead_time_ms",
        "packet_loss", "average_rtt", "feedback_category"
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        rec_cfg = self.config.get("recovery", {})
        self.stability_duration_sec = rec_cfg.get("stability_duration_sec", 15.0)
        self.healthy_samples_required = rec_cfg.get("healthy_samples_required", 10)
        self.max_acceptable_prob = rec_cfg.get("max_acceptable_failure_prob", 0.15)
        self.log_path = self.config.get("events", {}).get("log_path", "data/events.csv")

        # Performance counters
        self.stats = {
            "TRUE_POSITIVE": 0,
            "FALSE_POSITIVE": 0,
            "TRUE_NEGATIVE": 0,
            "FALSE_NEGATIVE": 0,
            "RECOVERY_SUCCESS": 0,
            "RECOVERY_FAILURE": 0,
            "total_lead_time_ms": 0.0,
            "lead_time_count": 0
        }

        # Timestamps for lead time tracking
        self.last_prediction_time: Optional[float] = None
        self.last_reroute_time: Optional[float] = None
        self.last_failure_time: Optional[float] = None

        # Anti-flapping state
        self.recovery_detected_time: Optional[float] = None
        self.consecutive_healthy_samples: int = 0
        self.primary_stable: bool = True

        self._init_event_log()

    def _init_event_log(self) -> None:
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.EVENT_LOG_HEADER)

    def record_prediction(self, prediction_result: Dict[str, Any]) -> None:
        """Records timestamp when AI predicts high failure risk."""
        prob = prediction_result.get("failure_probability", 0.0)
        if prob >= 0.75 and self.last_prediction_time is None:
            self.last_prediction_time = time.time()
            logger.info(f"[FEEDBACK] Prediction timestamp recorded: {self.last_prediction_time:.3f}")

    def record_reroute(self, action_result: Dict[str, Any]) -> None:
        """Records timestamp when proactive reroute was executed."""
        if action_result.get("should_reroute"):
            self.last_reroute_time = time.time()
            self.primary_stable = False
            logger.info(f"[FEEDBACK] Preemptive reroute timestamp: {self.last_reroute_time:.3f}")

    def record_failure_event(self, actual_failure: bool, current_loss: float) -> Optional[float]:
        """
        Calculates failure lead time when link collapses.
        lead_time_ms = failure_timestamp - prediction_timestamp.
        """
        if actual_failure and self.last_failure_time is None:
            self.last_failure_time = time.time()
            if self.last_prediction_time:
                lead_time_ms = round((self.last_failure_time - self.last_prediction_time) * 1000.0, 1)
                self.stats["total_lead_time_ms"] += lead_time_ms
                self.stats["lead_time_count"] += 1
                logger.info(f"[FEEDBACK EVALUATION] Achieved Failure Lead Time: {lead_time_ms} ms!")
                return lead_time_ms
        return None

    def evaluate_cycle(
        self,
        scenario: str,
        predicted_risk: float,
        actual_failure_occurred: bool,
        rerouted: bool,
        current_loss: float,
        current_rtt: float,
        device: str = "SW1",
        interface: str = "Gi0/1",
        selected_path: str = "PATH_PRIMARY"
    ) -> Dict[str, Any]:
        """
        Evaluates the classification and recovery success of the current cycle.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        lead_time = self.record_failure_event(actual_failure_occurred, current_loss)

        # Classification outcome
        predicted_fail = predicted_risk >= 0.75
        if predicted_fail and actual_failure_occurred:
            cat = "TRUE_POSITIVE"
        elif predicted_fail and not actual_failure_occurred:
            cat = "FALSE_POSITIVE"
        elif not predicted_fail and actual_failure_occurred:
            cat = "FALSE_NEGATIVE"
        else:
            cat = "TRUE_NEGATIVE"

        self.stats[cat] += 1

        # Recovery outcome
        recovery_status = "N/A"
        if actual_failure_occurred:
            if rerouted and current_loss < 5.0:
                recovery_status = "RECOVERY_SUCCESS"
                self.stats["RECOVERY_SUCCESS"] += 1
            else:
                recovery_status = "RECOVERY_FAILURE"
                self.stats["RECOVERY_FAILURE"] += 1

        # Write to event log
        event_row = [
            now_str, scenario, device, interface,
            "HIGH_RISK" if predicted_fail else "HEALTHY",
            round(predicted_risk, 3), 0.95,
            round(lead_time, 1) if lead_time else "",
            selected_path,
            "PREEMPTIVE_REROUTE" if rerouted else "MONITOR",
            "YES" if actual_failure_occurred else "NO",
            recovery_status,
            round(lead_time, 1) if lead_time else "",
            round(current_loss, 2),
            round(current_rtt, 2),
            cat
        ]
        self._append_event_log(event_row)

        return {
            "feedback_category": cat,
            "recovery_status": recovery_status,
            "lead_time_ms": lead_time,
            "stats": dict(self.stats)
        }

    def evaluate_restoration_hysteresis(
        self,
        primary_link_up: bool,
        primary_failure_prob: float
    ) -> Dict[str, Any]:
        """
        Anti-flapping hysteresis algorithm.
        Requires link to be physically UP and telemetry healthy (prob < 0.15)
        for consecutive samples or duration before recommending cost restoration.
        """
        now = time.time()

        if not primary_link_up:
            self.recovery_detected_time = None
            self.consecutive_healthy_samples = 0
            self.primary_stable = False
            return {
                "can_restore": False,
                "reason": "Primary link is physically DOWN.",
                "elapsed_stability_sec": 0.0,
                "healthy_samples": 0
            }

        # Primary is UP: check telemetry health
        if primary_failure_prob < self.max_acceptable_prob:
            self.consecutive_healthy_samples += 1
            if self.recovery_detected_time is None:
                self.recovery_detected_time = now
                logger.info("[HYSTERESIS] Primary link recovery detected! Starting anti-flapping stability timer.")

            elapsed = now - self.recovery_detected_time
            if elapsed >= self.stability_duration_sec or self.consecutive_healthy_samples >= self.healthy_samples_required:
                self.primary_stable = True
                logger.info(f"[HYSTERESIS COMPLETE] Primary link stable for {elapsed:.1f}s ({self.consecutive_healthy_samples} samples). Route restoration APPROVED.")
                return {
                    "can_restore": True,
                    "reason": f"Primary link stable for {elapsed:.1f}s ({self.consecutive_healthy_samples} consecutive healthy samples).",
                    "elapsed_stability_sec": round(elapsed, 1),
                    "healthy_samples": self.consecutive_healthy_samples
                }
            else:
                return {
                    "can_restore": False,
                    "reason": f"Stabilizing: {elapsed:.1f}s / {self.stability_duration_sec}s ({self.consecutive_healthy_samples}/{self.healthy_samples_required} samples).",
                    "elapsed_stability_sec": round(elapsed, 1),
                    "healthy_samples": self.consecutive_healthy_samples
                }
        else:
            # Telemetry is noisy/unhealthy during recovery attempt! Reset timer
            self.recovery_detected_time = None
            self.consecutive_healthy_samples = 0
            self.primary_stable = False
            return {
                "can_restore": False,
                "reason": f"Primary recovered but telemetry indicates residual instability (Risk: {primary_failure_prob*100:.1f}%). Holding timer.",
                "elapsed_stability_sec": 0.0,
                "healthy_samples": 0
            }

    def _append_event_log(self, row: List[Any]) -> None:
        try:
            with open(self.log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Failed logging event to {self.log_path}: {e}")

    def get_confusion_matrix(self) -> Dict[str, int]:
        return {
            "TP": self.stats["TRUE_POSITIVE"],
            "FP": self.stats["FALSE_POSITIVE"],
            "TN": self.stats["TRUE_NEGATIVE"],
            "FN": self.stats["FALSE_NEGATIVE"]
        }

    def get_average_lead_time_ms(self) -> float:
        if self.stats["lead_time_count"] == 0:
            return 0.0
        return round(self.stats["total_lead_time_ms"] / self.stats["lead_time_count"], 1)
