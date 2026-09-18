import os
from typing import Dict, Any, Optional, Tuple
import numpy as np

from src.utils.logger import logger

class TTFPredictor:
    """
    Time-to-Failure (TTF) Estimation Component.
    Projects remaining time before link degradation crosses the critical failure threshold
    using degradation trajectory extrapolation combined with trained regression modeling.
    Outputs point estimate and confidence interval [lower_bound, upper_bound].
    """

    def __init__(self, model_path: str = "models/ttf_model.pkl", config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.model_path = model_path
        self.model = None

        ttf_cfg = self.config.get("ttf", {})
        self.crit_loss = ttf_cfg.get("critical_loss_threshold_pct", 15.0)
        self.crit_rtt = ttf_cfg.get("critical_rtt_threshold_ms", 80.0)
        self.uncertainty_pct = ttf_cfg.get("uncertainty_margin_pct", 0.15)
        self.min_lead_time_ms = ttf_cfg.get("reroute_lead_time_min_ms", 300)
        self.max_lead_time_ms = ttf_cfg.get("reroute_lead_time_max_ms", 8000)

        self.load_model()

    def load_model(self) -> bool:
        if os.path.exists(self.model_path):
            try:
                import joblib
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded TTF regression model from {self.model_path}")
                return True
            except Exception as e:
                logger.warning(f"Could not load TTF model from {self.model_path}: {e}")
                self.model = None
                return False
        return False

    def estimate_ttf(self, features: Dict[str, float], failure_prob: float) -> Dict[str, Any]:
        """
        Estimates remaining milliseconds before link collapse.
        Returns estimated_ttf_ms, ttf_lower_ms, ttf_upper_ms, and estimation_method.
        """
        # If link is healthy or risk is low, TTF is nominal / not imminent
        if failure_prob < 0.40 and features.get("loss_mean_5", 0.0) < 1.0:
            return {
                "estimated_ttf_ms": None,
                "ttf_range_str": "> 10,000 ms (Stable)",
                "ttf_lower_ms": 10000,
                "ttf_upper_ms": 10000,
                "is_critical": False,
                "method": "STABLE_BASELINE"
            }

        # Trajectory physics: calculate velocity of degradation
        loss_curr = features.get("loss_current", 0.0)
        loss_slope = max(0.01, features.get("loss_slope_5", 0.0))
        rtt_curr = features.get("rtt_current", 12.0)
        rtt_slope = max(0.05, features.get("rtt_slope_5", 0.0))
        instability = features.get("instability_score", 10.0)

        # Time to hit critical packet loss threshold (e.g. 15%)
        # In a 1-second sample loop, slope is per sample (1000 ms)
        # delta_time_samples = (crit_loss - loss_curr) / slope
        loss_headroom = max(0.0, self.crit_loss - loss_curr)
        time_to_loss_fail_sec = loss_headroom / loss_slope

        # Time to hit critical RTT threshold
        rtt_headroom = max(0.0, self.crit_rtt - rtt_curr)
        time_to_rtt_fail_sec = rtt_headroom / rtt_slope

        # Combined trajectory estimate in ms
        # Weighted by metric severity
        if loss_curr > 5.0:
            projected_sec = min(time_to_loss_fail_sec, time_to_rtt_fail_sec)
        else:
            projected_sec = (0.6 * time_to_loss_fail_sec) + (0.4 * time_to_rtt_fail_sec)

        projected_ms = projected_sec * 1000.0

        # Adjust by instability score acceleration
        acceleration_factor = max(0.6, 1.0 - (instability / 200.0))
        estimated_ms = projected_ms * acceleration_factor

        # Clamp to realistic observed lead times [300 ms, 8000 ms]
        estimated_ms = max(float(self.min_lead_time_ms), min(float(self.max_lead_time_ms), estimated_ms))
        estimated_ms = round(estimated_ms, 0)

        # Uncertainty bounds
        margin = estimated_ms * self.uncertainty_pct
        lower_ms = max(100.0, round(estimated_ms - margin, 0))
        upper_ms = round(estimated_ms + margin, 0)

        return {
            "estimated_ttf_ms": int(estimated_ms),
            "ttf_lower_ms": int(lower_ms),
            "ttf_upper_ms": int(upper_ms),
            "ttf_range_str": f"{int(lower_ms)}–{int(upper_ms)} ms",
            "is_critical": estimated_ms <= 2500,
            "method": "PHYSICAL_TRAJECTORY_EXTRAPOLATION"
        }
