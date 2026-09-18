import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

from src.utils.logger import logger
from src.features.feature_engine import FeatureEngine

class FailurePredictor:
    """
    Lightweight, explainable Machine Learning Failure Prediction Engine.
    Uses DecisionTreeClassifier (with fallback rule-engine) to output:
    - Predicted State (0: HEALTHY, 1: WARNING, 2: HIGH_RISK)
    - Failure Probability [0.0, 1.0]
    - Model Confidence [0.0, 1.0]
    - Explainable Top Contributing Indicators
    """

    CLASS_NAMES = {
        0: "HEALTHY",
        1: "WARNING",
        2: "HIGH_RISK"
    }

    def __init__(self, model_path: str = "models/failure_model.pkl", config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.model_path = model_path
        self.model = None
        self.feature_names = FeatureEngine.FEATURE_NAMES
        self.load_model()

    def load_model(self) -> bool:
        """Loads serialized scikit-learn model from disk using joblib."""
        if os.path.exists(self.model_path):
            try:
                import joblib
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded failure prediction model from {self.model_path}")
                return True
            except Exception as e:
                logger.warning(f"Could not load ML model from {self.model_path}: {e}. Falling back to explainable heuristic rules.")
                self.model = None
                return False
        else:
            logger.info(f"Model file {self.model_path} not found yet. Operating in heuristic mode until train.py is executed.")
            self.model = None
            return False

    def predict(self, feature_dict: Dict[str, float]) -> Dict[str, Any]:
        """
        Executes failure prediction on an engineered feature dictionary.
        Returns state, failure probability, confidence, and top contributing indicators.
        """
        # Feature vector in exact order
        feat_vector = np.array([[feature_dict.get(k, 0.0) for k in self.feature_names]], dtype=float)

        if self.model is not None:
            try:
                pred_class_id = int(self.model.predict(feat_vector)[0])
                prob_dist = self.model.predict_proba(feat_vector)[0]

                # Map probability distribution to classes [0, 1, 2]
                # P(Failure) = P(HIGH_RISK) + 0.5 * P(WARNING)
                prob_healthy = float(prob_dist[0]) if len(prob_dist) > 0 else 0.0
                prob_warning = float(prob_dist[1]) if len(prob_dist) > 1 else 0.0
                prob_high_risk = float(prob_dist[2]) if len(prob_dist) > 2 else 0.0

                failure_prob = min(1.0, max(0.0, prob_high_risk + (0.5 * prob_warning)))
                confidence = float(np.max(prob_dist))

                indicators = self._extract_contributing_indicators(feature_dict)

                return {
                    "predicted_class_id": pred_class_id,
                    "predicted_class": self.CLASS_NAMES.get(pred_class_id, "UNKNOWN"),
                    "failure_probability": round(failure_prob, 3),
                    "confidence": round(confidence, 3),
                    "class_probabilities": {
                        "HEALTHY": round(prob_healthy, 3),
                        "WARNING": round(prob_warning, 3),
                        "HIGH_RISK": round(prob_high_risk, 3)
                    },
                    "contributing_indicators": indicators,
                    "inference_engine": "ML_DECISION_TREE"
                }
            except Exception as e:
                logger.warning(f"ML inference error: {e}. Utilizing fallback heuristics.")

        # Fallback explainable heuristic prediction
        return self._heuristic_predict(feature_dict)

    def _heuristic_predict(self, f: Dict[str, float]) -> Dict[str, Any]:
        """
        Deterministic, explainable rule-based inference aligned with domain network heuristics.
        """
        score = f.get("instability_score", 0.0)
        loss = f.get("loss_mean_5", 0.0)
        j_slope = f.get("jitter_slope_5", 0.0)
        crc_growth = f.get("crc_growth_5", 0.0)
        rtt_slope = f.get("rtt_slope_5", 0.0)
        flaps = f.get("flaps_current", 0)

        indicators = self._extract_contributing_indicators(f)

        if score >= 60.0 or loss >= 8.0 or j_slope >= 3.0 or crc_growth >= 10.0 or flaps >= 2:
            class_id = 2  # HIGH_RISK
            prob = min(0.98, 0.75 + (score / 400.0))
            conf = min(0.96, 0.82 + (loss / 50.0))
        elif score >= 25.0 or loss >= 2.0 or j_slope >= 1.0 or crc_growth >= 3.0:
            class_id = 1  # WARNING
            prob = 0.35 + (score / 100.0) * 0.35
            conf = 0.78
        else:
            class_id = 0  # HEALTHY
            prob = max(0.02, score / 200.0)
            conf = 0.94

        return {
            "predicted_class_id": class_id,
            "predicted_class": self.CLASS_NAMES[class_id],
            "failure_probability": round(prob, 3),
            "confidence": round(conf, 3),
            "class_probabilities": {
                "HEALTHY": round(1.0 - prob, 3),
                "WARNING": round(prob * 0.3, 3) if class_id != 0 else 0.05,
                "HIGH_RISK": round(prob, 3) if class_id == 2 else 0.02
            },
            "contributing_indicators": indicators,
            "inference_engine": "HEURISTIC_RULE_FALLBACK"
        }

    def _extract_contributing_indicators(self, f: Dict[str, float]) -> List[str]:
        """Identifies key metrics that triggered or elevated failure risk."""
        reasons = []
        if f.get("jitter_slope_5", 0.0) > 1.2:
            reasons.append(f"Jitter accelerating rapidly (+{f['jitter_slope_5']:.2f} ms/sample)")
        if f.get("loss_slope_5", 0.0) > 0.5 or f.get("loss_mean_5", 0.0) > 1.0:
            reasons.append(f"Packet loss trend increasing (current avg: {f.get('loss_mean_5', 0.0):.1f}%)")
        if f.get("crc_growth_5", 0.0) > 2.0:
            reasons.append(f"CRC frame alignment errors accumulating (+{int(f['crc_growth_5'])} errors in 5 samples)")
        if f.get("rtt_slope_5", 0.0) > 2.0:
            reasons.append(f"RTT slope trending upwards (+{f['rtt_slope_5']:.2f} ms/sample)")
        if f.get("flaps_current", 0) > 0:
            reasons.append(f"Physical interface flap instability detected ({int(f['flaps_current'])} flaps)")
        if f.get("instability_score", 0.0) > 50.0:
            reasons.append(f"Composite link instability index elevated ({f['instability_score']:.1f}/100)")

        if not reasons:
            reasons.append("All monitored telemetry dimensions within nominal baseline thresholds.")
        return reasons
