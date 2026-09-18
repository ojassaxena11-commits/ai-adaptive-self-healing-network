import os
import json
import random
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

from src.utils.logger import logger
from src.features.feature_engine import FeatureEngine

def generate_synthetic_training_data(n_episodes: int = 150) -> pd.DataFrame:
    """
    Generates realistic time-series degradation trajectories representing:
    Class 0: Healthy links (stable baseline)
    Class 1: Warning / Degrading links (moderate drift, jitter rise)
    Class 2: High Risk links (rapid acceleration, error growth, interface flaps)
    """
    logger.info(f"Generating synthetic telemetry dataset across {n_episodes} time-series episodes...")
    records = []

    for ep in range(n_episodes):
        # 40% healthy, 30% warning/degrading, 30% severe failure
        profile = random.choices(["HEALTHY", "WARNING", "HIGH_RISK"], weights=[0.40, 0.30, 0.30])[0]
        steps = random.randint(15, 30)

        # Baseline conditions
        rtt = random.uniform(8.0, 16.0)
        jitter = random.uniform(0.5, 2.5)
        loss = 0.0
        crc_cum = random.randint(0, 5)
        err_cum = crc_cum
        flaps = 0
        util = random.uniform(20.0, 45.0)

        for s in range(steps):
            if profile == "HEALTHY":
                rtt = max(6.0, rtt + random.gauss(0, 0.5))
                jitter = max(0.2, jitter + random.gauss(0, 0.2))
                loss = 0.0 if random.random() > 0.01 else 0.1
                crc_cum += 1 if random.random() < 0.03 else 0
                err_cum = crc_cum
                flaps = 0
                util = max(10.0, min(80.0, util + random.gauss(0, 1.5)))
                label = 0
                ttf_ms = 10000.0

            elif profile == "WARNING":
                # Gradual drift
                drift_factor = s / float(steps)
                rtt = max(8.0, rtt + (drift_factor * 1.5) + random.gauss(0, 0.6))
                jitter = max(0.5, jitter + (drift_factor * 0.8) + random.gauss(0, 0.3))
                loss = max(0.0, (drift_factor * 2.2) + random.gauss(0, 0.2))
                crc_cum += int(random.random() < 0.25)
                err_cum = crc_cum + int(drift_factor * 2)
                flaps = 0
                util = min(85.0, util + (drift_factor * 2.0))
                label = 1
                ttf_ms = max(2500.0, 6000.0 - (s * 150.0) + random.gauss(0, 200.0))

            else:  # HIGH_RISK
                # Accelerating degradation
                accel = (s / float(steps)) ** 1.8
                rtt = rtt + (accel * 4.5) + random.gauss(0, 1.0)
                jitter = jitter + (accel * 2.8) + random.gauss(0, 0.5)
                loss = min(100.0, max(0.0, (accel * 8.5) + random.gauss(0, 0.5)))
                crc_cum += int(accel * 3.5 + random.randint(1, 3))
                err_cum = crc_cum + int(accel * 2.5)
                flaps = int(accel > 0.6) + (1 if accel > 0.85 else 0)
                util = min(98.0, util + (accel * 4.0))

                # Transition from Warning to High Risk as acceleration peaks
                if accel < 0.35:
                    label = 1
                    ttf_ms = 4000.0 - (s * 100.0)
                else:
                    label = 2
                    ttf_ms = max(400.0, 2200.0 - (s * 90.0) + random.gauss(0, 100.0))

            records.append({
                "episode": ep,
                "step": s,
                "rtt": round(rtt, 2),
                "jitter": round(jitter, 2),
                "packet_loss": round(loss, 2),
                "crc_errors": crc_cum,
                "interface_errors": err_cum,
                "interface_flaps": flaps,
                "utilization": round(util, 2),
                "label": label,
                "ttf_ms": round(ttf_ms, 1)
            })

    raw_df = pd.DataFrame(records)
    logger.info(f"Generated {len(raw_df)} raw synthetic telemetry samples.")
    return raw_df

def train_and_evaluate_models() -> Dict[str, Any]:
    """
    Executes end-to-end ML and TTF training pipeline:
    1. Feature engineering with rolling window slopes.
    2. DecisionTreeClassifier training with explainable inspection.
    3. RandomForest and LogisticRegression benchmark comparisons.
    4. GradientBoostingRegressor / LinearRegression for TTF estimation.
    5. Saves serialized models (.pkl) and quantitative performance metadata (.json).
    """
    import joblib
    import matplotlib.pyplot as plt
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        confusion_matrix, mean_absolute_error, mean_squared_error
    )

    # 1. Generate Raw Data
    raw_df = generate_synthetic_training_data(n_episodes=180)
    os.makedirs("data", exist_ok=True)
    raw_df.to_csv("data/training.csv", index=False)

    # 2. Extract Features Episode-by-Episode
    fe = FeatureEngine()
    feature_rows = []

    for ep_id, group in raw_df.groupby("episode"):
        for i in range(len(group)):
            sub_history = group.iloc[: i + 1]
            feats = fe.extract_features(sub_history)
            row = dict(feats)
            row["label"] = group.iloc[i]["label"]
            row["ttf_ms"] = group.iloc[i]["ttf_ms"]
            feature_rows.append(row)

    dataset_df = pd.DataFrame(feature_rows)
    feature_cols = fe.FEATURE_NAMES

    X = dataset_df[feature_cols].values
    y = dataset_df["label"].values
    y_ttf = dataset_df["ttf_ms"].values

    X_train, X_test, y_train, y_test, ttf_train, ttf_test = train_test_split(
        X, y, y_ttf, test_size=0.25, random_state=42, stratify=y
    )

    # 3. Train Primary Model: DecisionTreeClassifier
    logger.info("Training primary explainable DecisionTreeClassifier...")
    dt_model = DecisionTreeClassifier(max_depth=5, criterion="entropy", random_state=42)
    dt_model.fit(X_train, y_train)
    dt_preds = dt_model.predict(X_test)

    # Calculate Metrics
    dt_acc = accuracy_score(y_test, dt_preds)
    p_prec, p_rec, p_f1, _ = precision_recall_fscore_support(y_test, dt_preds, average=None, labels=[0, 1, 2])
    macro_f1 = float(np.mean(p_f1))
    cm = confusion_matrix(y_test, dt_preds, labels=[0, 1, 2])

    logger.info(f"DecisionTree Accuracy: {dt_acc*100:.2f}% | Macro F1: {macro_f1:.4f}")

    # 4. Train Comparison Baseline Models
    logger.info("Training comparison baseline models (RandomForest & LogisticRegression)...")
    rf_model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    rf_model.fit(X_train, y_train)
    rf_acc = accuracy_score(y_test, rf_model.predict(X_test))

    lr_model = LogisticRegression(max_iter=1000, random_state=42)
    lr_model.fit(X_train, y_train)
    lr_acc = accuracy_score(y_test, lr_model.predict(X_test))

    logger.info(f"Model Comparison -> DT: {dt_acc*100:.2f}% | RF: {rf_acc*100:.2f}% | LR: {lr_acc*100:.2f}%")

    # 5. Train TTF Regressor
    logger.info("Training Time-to-Failure (TTF) Regressor...")
    # Train TTF on degrading / high-risk samples
    mask_train = y_train > 0
    mask_test = y_test > 0
    ttf_reg = GradientBoostingRegressor(n_estimators=60, max_depth=3, random_state=42)
    ttf_reg.fit(X_train[mask_train], ttf_train[mask_train])

    ttf_preds = ttf_reg.predict(X_test[mask_test])
    mae = mean_absolute_error(ttf_test[mask_test], ttf_preds)
    rmse = np.sqrt(mean_squared_error(ttf_test[mask_test], ttf_preds))
    logger.info(f"TTF Model Performance -> MAE: {mae:.1f} ms | RMSE: {rmse:.1f} ms")

    # 6. Feature Importances
    importances = dict(zip(feature_cols, [round(float(v), 4) for v in dt_model.feature_importances_]))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
    logger.info(f"Top 5 Contributing Features: {top_features}")

    # 7. Save Models and Metadata
    os.makedirs("models", exist_ok=True)
    joblib.dump(dt_model, "models/failure_model.pkl")
    joblib.dump(ttf_reg, "models/ttf_model.pkl")

    metadata = {
        "primary_model": "DecisionTreeClassifier",
        "accuracy": round(float(dt_acc), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_class_metrics": {
            "HEALTHY": {"precision": round(float(p_prec[0]), 3), "recall": round(float(p_rec[0]), 3), "f1": round(float(p_f1[0]), 3)},
            "WARNING": {"precision": round(float(p_prec[1]), 3), "recall": round(float(p_rec[1]), 3), "f1": round(float(p_f1[1]), 3)},
            "HIGH_RISK": {"precision": round(float(p_prec[2]), 3), "recall": round(float(p_rec[2]), 3), "f1": round(float(p_f1[2]), 3)},
        },
        "confusion_matrix": cm.tolist(),
        "baseline_comparison": {
            "DecisionTreeClassifier_accuracy": round(float(dt_acc), 4),
            "RandomForestClassifier_accuracy": round(float(rf_acc), 4),
            "LogisticRegression_accuracy": round(float(lr_acc), 4)
        },
        "ttf_metrics": {
            "mae_ms": round(float(mae), 1),
            "rmse_ms": round(float(rmse), 1)
        },
        "feature_importances": importances
    }

    with open("models/model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 8. Render Confusion Matrix Plot
    os.makedirs("results/graphs", exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
    cax = ax.matshow(cm, cmap="Blues", alpha=0.85)
    for (i, j), z in np.ndenumerate(cm):
        ax.text(j, i, f"{z}", ha="center", va="center", fontsize=11, fontweight="bold")
    fig.colorbar(cax)
    classes = ["Healthy (0)", "Warning (1)", "High Risk (2)"]
    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(classes, fontsize=9)
    ax.set_yticklabels(classes, fontsize=9)
    plt.title("ML Failure Prediction Confusion Matrix", fontsize=11, fontweight="bold", pad=15)
    plt.xlabel("Predicted Class", fontsize=10)
    plt.ylabel("Ground Truth Class", fontsize=10)
    plt.tight_layout()
    plt.savefig("results/graphs/confusion_matrix.png")
    plt.close()

    logger.info("Training pipeline complete! Models and graphs saved successfully.")
    return metadata

if __name__ == "__main__":
    train_and_evaluate_models()
