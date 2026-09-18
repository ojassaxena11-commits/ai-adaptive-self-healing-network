from typing import Dict, Any, List, Optional
from src.utils.logger import logger

class PathEvaluator:
    """
    Multi-Factor Path Evaluation & Traffic-Aware QoS Engine.
    Computes comparative objective path penalty scores across candidate network paths:
    Path A (Primary via SW1-SW2) vs Path B (Backup via SW1-SW3-SW2).
    Dynamically re-weights latency, packet loss, utilization, hop count, and predicted risk
    based on application traffic class (VOIP, VIDEO, NORMAL_DATA).
    """

    DEFAULT_PROFILES = {
        "VOIP": {
            "name": "Voice over IP",
            "weights": {
                "latency": 0.30,
                "packet_loss": 0.35,
                "utilization": 0.05,
                "path_risk": 0.20,
                "hop_count": 0.10
            },
            "constraints": {"max_rtt_ms": 50.0, "max_loss_pct": 1.0}
        },
        "VIDEO": {
            "name": "Real-time Video Streaming",
            "weights": {
                "latency": 0.15,
                "packet_loss": 0.25,
                "utilization": 0.35,
                "path_risk": 0.15,
                "hop_count": 0.10
            },
            "constraints": {"max_rtt_ms": 100.0, "max_loss_pct": 2.5}
        },
        "NORMAL_DATA": {
            "name": "Best-Effort Data (TCP)",
            "weights": {
                "latency": 0.20,
                "packet_loss": 0.15,
                "utilization": 0.20,
                "path_risk": 0.20,
                "hop_count": 0.25
            },
            "constraints": {"max_rtt_ms": 200.0, "max_loss_pct": 5.0}
        }
    }

    # Reference normalization upper bounds
    MAX_RTT_NORM = 150.0
    MAX_LOSS_NORM = 20.0
    MAX_UTIL_NORM = 100.0
    MAX_HOPS_NORM = 6.0

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.qos_profiles = self.config.get("qos_profiles", self.DEFAULT_PROFILES)

    def evaluate_paths(
        self,
        candidate_paths: List[Dict[str, Any]],
        traffic_class: str = "NORMAL_DATA"
    ) -> Dict[str, Any]:
        """
        Evaluates a list of candidate path telemetry dictionaries.
        Returns:
        - ranked_paths: list of candidate paths with calculated scores, sorted lowest to highest (best first)
        - best_path: the optimal path dictionary
        - traffic_class: applied QoS profile
        """
        profile = self.qos_profiles.get(traffic_class, self.qos_profiles.get("NORMAL_DATA", self.DEFAULT_PROFILES["NORMAL_DATA"]))
        weights = profile.get("weights", self.DEFAULT_PROFILES["NORMAL_DATA"]["weights"])
        constraints = profile.get("constraints", {})

        evaluated = []
        for p in candidate_paths:
            p_copy = dict(p)
            rtt = float(p_copy.get("rtt", 15.0))
            loss = float(p_copy.get("packet_loss", 0.0))
            util = float(p_copy.get("utilization", 30.0))
            risk = float(p_copy.get("risk", 0.0))
            hops = float(p_copy.get("hops", 3.0))

            # Normalized components [0.0, 1.0]
            norm_lat = min(1.0, rtt / self.MAX_RTT_NORM)
            norm_loss = min(1.0, loss / self.MAX_LOSS_NORM)
            norm_util = min(1.0, util / self.MAX_UTIL_NORM)
            norm_risk = min(1.0, max(0.0, risk))
            norm_hops = min(1.0, hops / self.MAX_HOPS_NORM)

            # QoS constraint penalty
            qos_penalty = 0.0
            if rtt > constraints.get("max_rtt_ms", 999.0):
                qos_penalty += 0.35
            if loss > constraints.get("max_loss_pct", 100.0):
                qos_penalty += 0.50

            # Composite Score (Lower is better)
            score = (
                (weights.get("latency", 0.25) * norm_lat) +
                (weights.get("packet_loss", 0.30) * norm_loss) +
                (weights.get("utilization", 0.15) * norm_util) +
                (weights.get("path_risk", 0.20) * norm_risk) +
                (weights.get("hop_count", 0.10) * norm_hops) +
                qos_penalty
            )
            p_copy["score"] = round(score, 4)
            p_copy["qos_penalty"] = round(qos_penalty, 3)
            evaluated.append(p_copy)

        # Sort paths by score ascending (lowest penalty is best)
        ranked = sorted(evaluated, key=lambda x: x["score"])
        best = ranked[0] if ranked else {}

        return {
            "traffic_class": traffic_class,
            "profile_name": profile.get("name", traffic_class),
            "weights_used": weights,
            "ranked_paths": ranked,
            "best_path": best
        }
