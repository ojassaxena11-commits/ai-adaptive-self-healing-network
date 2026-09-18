import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

class FeatureEngine:
    """
    Time-series feature engineering engine for network telemetry.
    Computes rolling averages, moving variances, linear slopes (trend/velocity),
    rate of error growth, and composite instability scores across configurable windows.
    """

    FEATURE_NAMES = [
        "rtt_current", "rtt_mean_5", "rtt_std_5", "rtt_slope_5", "rtt_mean_10", "rtt_slope_10",
        "jitter_current", "jitter_mean_5", "jitter_std_5", "jitter_slope_5", "jitter_slope_10",
        "loss_current", "loss_mean_5", "loss_slope_5", "loss_slope_10",
        "crc_current", "crc_growth_5", "crc_growth_10",
        "err_current", "err_growth_5",
        "flaps_current",
        "util_current", "util_mean_5", "util_slope_5",
        "instability_score"
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        feat_cfg = self.config.get("features", {})
        self.rolling_windows = feat_cfg.get("rolling_windows", [5, 10, 20])
        self.weights = feat_cfg.get("instability_weights", {
            "loss_rate": 0.35,
            "jitter_slope": 0.25,
            "crc_growth": 0.25,
            "interface_flaps": 0.15
        })

    @staticmethod
    def calculate_linear_slope(values: np.ndarray) -> float:
        """
        Calculates ordinary least-squares linear regression slope (rate of change per sample).
        y = mx + c  -> returns m.
        """
        n = len(values)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.asarray(values, dtype=float)

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        denominator = np.sum((x - x_mean) ** 2)
        if denominator == 0.0:
            return 0.0

        numerator = np.sum((x - x_mean) * (y - y_mean))
        return float(numerator / denominator)

    def extract_features(self, history_df: pd.DataFrame) -> Dict[str, float]:
        """
        Extracts engineered time-series features from recent telemetry history.
        Expects a DataFrame with at least 1 row, containing:
        rtt, jitter, packet_loss, crc_errors, interface_errors, interface_flaps, utilization.
        """
        if history_df.empty:
            return {feat: 0.0 for feat in self.FEATURE_NAMES}

        # Current (most recent) values
        latest = history_df.iloc[-1]
        rtt_curr = float(latest.get("rtt", 0.0))
        jitter_curr = float(latest.get("jitter", 0.0))
        loss_curr = float(latest.get("packet_loss", 0.0))
        crc_curr = float(latest.get("crc_errors", 0.0))
        err_curr = float(latest.get("interface_errors", 0.0))
        flaps_curr = float(latest.get("interface_flaps", 0.0))
        util_curr = float(latest.get("utilization", 0.0))

        # Windows
        w5_df = history_df.tail(5)
        w10_df = history_df.tail(10)

        # RTT Features
        rtt_arr_5 = w5_df["rtt"].values.astype(float)
        rtt_arr_10 = w10_df["rtt"].values.astype(float)
        rtt_mean_5 = float(np.mean(rtt_arr_5))
        rtt_std_5 = float(np.std(rtt_arr_5)) if len(rtt_arr_5) > 1 else 0.0
        rtt_slope_5 = self.calculate_linear_slope(rtt_arr_5)
        rtt_mean_10 = float(np.mean(rtt_arr_10))
        rtt_slope_10 = self.calculate_linear_slope(rtt_arr_10)

        # Jitter Features
        jit_arr_5 = w5_df["jitter"].values.astype(float)
        jit_arr_10 = w10_df["jitter"].values.astype(float)
        jitter_mean_5 = float(np.mean(jit_arr_5))
        jitter_std_5 = float(np.std(jit_arr_5)) if len(jit_arr_5) > 1 else 0.0
        jitter_slope_5 = self.calculate_linear_slope(jit_arr_5)
        jitter_slope_10 = self.calculate_linear_slope(jit_arr_10)

        # Packet Loss Features
        loss_arr_5 = w5_df["packet_loss"].values.astype(float)
        loss_arr_10 = w10_df["packet_loss"].values.astype(float)
        loss_mean_5 = float(np.mean(loss_arr_5))
        loss_slope_5 = self.calculate_linear_slope(loss_arr_5)
        loss_slope_10 = self.calculate_linear_slope(loss_arr_10)

        # CRC Error Growth (difference over window)
        crc_arr_5 = w5_df["crc_errors"].values.astype(float)
        crc_growth_5 = float(crc_arr_5[-1] - crc_arr_5[0]) if len(crc_arr_5) > 1 else 0.0

        crc_arr_10 = w10_df["crc_errors"].values.astype(float)
        crc_growth_10 = float(crc_arr_10[-1] - crc_arr_10[0]) if len(crc_arr_10) > 1 else 0.0

        # Interface Errors Growth
        err_arr_5 = w5_df["interface_errors"].values.astype(float)
        err_growth_5 = float(err_arr_5[-1] - err_arr_5[0]) if len(err_arr_5) > 1 else 0.0

        # Utilization Features
        util_arr_5 = w5_df["utilization"].values.astype(float)
        util_mean_5 = float(np.mean(util_arr_5))
        util_slope_5 = self.calculate_linear_slope(util_arr_5)

        # Composite Instability Score [0.0, 100.0]
        # Combines loss rate, normalized positive slopes, CRC growth, and flaps
        w_loss = self.weights.get("loss_rate", 0.35)
        w_jit = self.weights.get("jitter_slope", 0.25)
        w_crc = self.weights.get("crc_growth", 0.25)
        w_flap = self.weights.get("interface_flaps", 0.15)

        norm_loss = min(100.0, loss_mean_5 * 5.0)
        norm_jit_slope = min(100.0, max(0.0, jitter_slope_5 * 15.0))
        norm_crc_growth = min(100.0, max(0.0, crc_growth_5 * 10.0))
        norm_flaps = min(100.0, flaps_curr * 25.0)

        instability_score = (
            (w_loss * norm_loss) +
            (w_jit * norm_jit_slope) +
            (w_crc * norm_crc_growth) +
            (w_flap * norm_flaps)
        )
        instability_score = round(float(min(100.0, max(0.0, instability_score))), 2)

        return {
            "rtt_current": round(rtt_curr, 2),
            "rtt_mean_5": round(rtt_mean_5, 2),
            "rtt_std_5": round(rtt_std_5, 2),
            "rtt_slope_5": round(rtt_slope_5, 3),
            "rtt_mean_10": round(rtt_mean_10, 2),
            "rtt_slope_10": round(rtt_slope_10, 3),
            "jitter_current": round(jitter_curr, 2),
            "jitter_mean_5": round(jitter_mean_5, 2),
            "jitter_std_5": round(jitter_std_5, 2),
            "jitter_slope_5": round(jitter_slope_5, 3),
            "jitter_slope_10": round(jitter_slope_10, 3),
            "loss_current": round(loss_curr, 2),
            "loss_mean_5": round(loss_mean_5, 2),
            "loss_slope_5": round(loss_slope_5, 3),
            "loss_slope_10": round(loss_slope_10, 3),
            "crc_current": int(crc_curr),
            "crc_growth_5": round(crc_growth_5, 2),
            "crc_growth_10": round(crc_growth_10, 2),
            "err_current": int(err_curr),
            "err_growth_5": round(err_growth_5, 2),
            "flaps_current": int(flaps_curr),
            "util_current": round(util_curr, 2),
            "util_mean_5": round(util_mean_5, 2),
            "util_slope_5": round(util_slope_5, 3),
            "instability_score": instability_score
        }
