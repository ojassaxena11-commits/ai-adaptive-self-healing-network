from typing import Dict, Any, Optional
from src.utils.logger import logger

class DecisionEngine:
    """
    Confidence-Gated, Risk-Aware Self-Healing Decision Engine.
    Evaluates failure risk, ML confidence, TTF horizons, backup path health,
    and traffic class constraints before issuing network reconfiguration orders.
    Enforces DRY_RUN safety modes and avoids route flapping.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        dec_cfg = self.config.get("decision", {})
        ml_cfg = self.config.get("ml", {})

        self.dry_run = dec_cfg.get("dry_run", False)
        self.prob_threshold = ml_cfg.get("failure_probability_threshold", 0.75)
        self.conf_threshold = ml_cfg.get("confidence_threshold", 0.80)

    def set_dry_run(self, dry_run: bool) -> None:
        """Toggles dry run mode."""
        self.dry_run = dry_run

    def evaluate(
        self,
        prediction_result: Dict[str, Any],
        ttf_result: Dict[str, Any],
        primary_link_status: str,
        best_candidate_path: Dict[str, Any],
        current_active_path_id: str = "PATH_PRIMARY",
        traffic_class: str = "NORMAL_DATA"
    ) -> Dict[str, Any]:
        """
        Executes policy decision.
        Returns action dictionary:
        - action: 'NO_ACTION' | 'INCREASE_MONITORING' | 'PREEMPTIVE_REROUTE' | 'HOLD_UNCONFIRMED' | 'RESTORATION_HYSTERESIS'
        - should_reroute: bool
        - target_path_id: str
        - reason: str
        - confidence_check_passed: bool
        - dry_run: bool
        """
        prob = prediction_result.get("failure_probability", 0.0)
        conf = prediction_result.get("confidence", 0.0)
        pred_class = prediction_result.get("predicted_class", "HEALTHY")
        ttf_ms = ttf_result.get("estimated_ttf_ms")
        indicators = prediction_result.get("contributing_indicators", [])

        conf_passed = conf >= self.conf_threshold
        prob_passed = prob >= self.prob_threshold

        # If already on backup path, check if primary is stable or if backup is failing
        if current_active_path_id == "PATH_BACKUP":
            # Link is currently diverted to backup
            return {
                "action": "MAINTAIN_BACKUP",
                "should_reroute": False,
                "target_path_id": "PATH_BACKUP",
                "reason": "Traffic already utilizing backup path. Hysteresis engine actively monitoring primary for recovery.",
                "confidence_check_passed": conf_passed,
                "dry_run": self.dry_run
            }

        # Case 1: Low Risk (Healthy)
        if prob < 0.40 and pred_class == "HEALTHY":
            return {
                "action": "NO_ACTION",
                "should_reroute": False,
                "target_path_id": "PATH_PRIMARY",
                "reason": f"Primary link operating nominally (Failure Risk: {prob*100:.1f}%, Confidence: {conf*100:.1f}%).",
                "confidence_check_passed": conf_passed,
                "dry_run": self.dry_run
            }

        # Case 2: Medium Risk (Warning / Incipient Drift)
        if 0.40 <= prob < self.prob_threshold:
            return {
                "action": "INCREASE_MONITORING",
                "should_reroute": False,
                "target_path_id": "PATH_PRIMARY",
                "reason": f"Telemetry drift detected (Risk: {prob*100:.1f}%). Polling frequency increased; awaiting trend confirmation.",
                "confidence_check_passed": conf_passed,
                "dry_run": self.dry_run
            }

        # Case 3: High Risk but Insufficient Confidence (Potential False Alarm / Anomaly)
        if prob_passed and not conf_passed:
            return {
                "action": "HOLD_UNCONFIRMED",
                "should_reroute": False,
                "target_path_id": "PATH_PRIMARY",
                "reason": f"High failure risk ({prob*100:.1f}%) detected, but model confidence ({conf*100:.1f}%) < threshold ({self.conf_threshold*100:.1f}%). Holding reroute to prevent route flapping.",
                "confidence_check_passed": False,
                "dry_run": self.dry_run
            }

        # Case 4: High Risk + High Confidence -> Evaluate Backup Health
        if prob_passed and conf_passed:
            # Check candidate backup quality
            backup_score = best_candidate_path.get("score", 999.0)
            backup_loss = best_candidate_path.get("packet_loss", 0.0)
            backup_risk = best_candidate_path.get("risk", 0.0)

            if backup_risk >= 0.70 or backup_loss >= 10.0:
                # Backup path is also unhealthy!
                return {
                    "action": "ABORT_CONGESTED_BACKUP",
                    "should_reroute": False,
                    "target_path_id": "PATH_PRIMARY",
                    "reason": f"Primary link at risk ({prob*100:.1f}%), but candidate backup path ({best_candidate_path.get('path_id')}) is congested/degraded (Loss: {backup_loss:.1f}%). Preemptive diversion rejected.",
                    "confidence_check_passed": True,
                    "dry_run": self.dry_run
                }

            # Preemptive Reroute Approved!
            lead_time_info = f"TTF: {ttf_ms} ms" if ttf_ms else "TTF: Imminent"
            reason_str = (
                f"High failure risk ({prob*100:.1f}%) with {conf*100:.1f}% confidence. "
                f"{lead_time_info}. Preemptively migrating traffic to healthy backup path "
                f"'{best_candidate_path.get('name')}' (Score: {backup_score:.2f})."
            )

            if self.dry_run:
                logger.warning(f"[DRY_RUN] Would trigger preemptive reroute: {reason_str}")

            return {
                "action": "PREEMPTIVE_REROUTE",
                "should_reroute": True,
                "target_path_id": best_candidate_path.get("path_id", "PATH_BACKUP"),
                "target_interface": best_candidate_path.get("interface", "GigabitEthernet0/2"),
                "reason": reason_str,
                "confidence_check_passed": True,
                "dry_run": self.dry_run
            }

        # Default fallback
        return {
            "action": "NO_ACTION",
            "should_reroute": False,
            "target_path_id": "PATH_PRIMARY",
            "reason": "Default monitoring state.",
            "confidence_check_passed": conf_passed,
            "dry_run": self.dry_run
        }
