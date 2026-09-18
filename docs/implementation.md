# Technical Implementation Details: AI-Driven Adaptive Self-Healing Network

This document provides in-depth technical documentation of the modules, classes, algorithms, and mathematical formulations powering the self-healing network prototype.

---

## 1. Package Architecture & Code Layout

The project follows a clean decoupled design separated into domain packages:

```text
src/
├── telemetry/          # Ingestion, parsing, and multi-scenario link degradation simulation
│   ├── collector.py    # Unified collector polling SSH/CML API with simulator fallback
│   ├── parser.py       # Regex parsers for Cisco IOS command outputs
│   └── simulator.py    # Time-series multi-condition network state generator
├── features/           # Time-series trend analytics & rolling statistics
│   └── feature_engine.py # Linear regression slopes, rolling variances, instability score
├── prediction/         # Machine learning inference & lead time estimation
│   ├── failure_predictor.py # DecisionTreeClassifier with explainable indicator extraction
│   └── ttf_predictor.py     # Trajectory velocity extrapolation and regression
├── decision/           # Confidence gating and policy enforcement
│   └── decision_engine.py   # Threshold arbitration and dry-run safety interception
├── routing/            # Path selection, traffic QoS, and Cisco network automation
│   ├── path_evaluator.py    # Multi-factor penalty scoring across VOIP, Video, Data
│   └── cisco_controller.py  # Netmiko SSH, CML REST, and simulated Cisco IOS mutations
├── feedback/           # Performance tracking & anti-flapping route restoration
│   └── feedback_engine.py   # Confusion classification, lead time, and hysteresis timer
├── experiments/        # Benchmarking and comparative analysis
│   ├── reactive_experiment.py # Standard OSPF dead-interval convergence measurement
│   ├── proactive_experiment.py# AI proactive self-healing measurement
│   └── compare_experiments.py # Comparison analysis and chart generation
├── dashboard/          # Professional Streamlit NOC dashboard
│   └── dashboard.py
└── utils/              # Cross-cutting logging and configuration loaders
    ├── logger.py
    └── config_loader.py
```

---

## 2. Mathematical Formulations & Algorithms

### 2.1 Trend Slope Derivation (Rate of Change)
For any metric $Y = [y_0, y_1, \dots, y_{W-1}]$ across sliding window $W$:
Let $X = [0, 1, \dots, W-1]$. The slope $m$ is derived using closed-form Ordinary Least Squares:
$$\bar{x} = \frac{W - 1}{2}, \quad \bar{y} = \frac{1}{W} \sum_{k=0}^{W-1} y_k$$
$$\text{Slope}_W(Y) = \frac{\sum_{k=0}^{W-1} (k - \bar{x})(y_k - \bar{y})}{\sum_{k=0}^{W-1} (k - \bar{x})^2}$$

### 2.2 Composite Link Instability Index
To aggregate heterogeneous dimensions into a unified risk indicator in $[0.0, 100.0]$:
$$I_t = w_{loss} \cdot \tilde{L}_t + w_{jit} \cdot \tilde{S}_{jitter} + w_{crc} \cdot \tilde{G}_{crc} + w_{flap} \cdot \tilde{F}_t$$
Where:
- $\tilde{L}_t = \min(100, \mu_5(\text{Loss}) \times 5.0)$
- $\tilde{S}_{jitter} = \min(100, \max(0, \text{Slope}_5(\text{Jitter}) \times 15.0))$
- $\tilde{G}_{crc} = \min(100, \max(0, \Delta CRC_5 \times 10.0))$
- $\tilde{F}_t = \min(100, \text{Flaps}_t \times 25.0)$
- Configured weights: $w_{loss}=0.35, w_{jit}=0.25, w_{crc}=0.25, w_{flap}=0.15$.

### 2.3 Time-to-Failure (TTF) Extrapolation
Given critical loss ceiling $L_{crit} = 15.0\%$ and current loss $L_t$:
$$\tau_{loss} = \frac{\max(0, L_{crit} - L_t)}{\max(\epsilon, \text{Slope}_5(L))} \times 1000 \text{ ms}$$
Projected TTF is damped by the instability acceleration factor:
$$\widehat{\text{TTF}} = \tau \times \max\left(0.6, 1.0 - \frac{I_t}{200}\right)$$
Uncertainty interval:
$$\text{Range} = [\max(100, \widehat{\text{TTF}} \times 0.85), \widehat{\text{TTF}} \times 1.15] \text{ ms}$$

### 2.4 Traffic-Aware QoS Path Evaluation
For candidate path $P$ with latency $L$, loss $P_L$, utilization $U$, predicted risk $R$, and hops $H$:
$$\text{Score}(P) = w_{lat} \frac{L}{150} + w_{loss} \frac{P_L}{20} + w_{util} \frac{U}{100} + w_{risk} R + w_{hop} \frac{H}{6} + \text{Penalty}_{QoS}$$

Application Profile Matrices:
| Profile | $w_{lat}$ | $w_{loss}$ | $w_{util}$ | $w_{risk}$ | $w_{hop}$ | Constraint Thresholds |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **VOIP** | 0.30 | 0.35 | 0.05 | 0.20 | 0.10 | Max RTT: 50ms, Max Loss: 1.0% |
| **VIDEO** | 0.15 | 0.25 | 0.35 | 0.15 | 0.10 | Max RTT: 100ms, Max Loss: 2.5% |
| **NORMAL_DATA**| 0.20 | 0.15 | 0.20 | 0.20 | 0.25 | Max RTT: 200ms, Max Loss: 5.0% |

---

## 3. Anti-Flapping Route Restoration Hysteresis

To eliminate route flapping when an intermittent primary link bounces up and down:
1. When the primary link transitions from `DOWN` to `UP`, the controller starts the stability observation clock: $t_{recovery} = t_{now}$.
2. The controller continuously checks two convergence criteria:
   - **Time Duration**: $t_{now} - t_{recovery} \ge 15.0 \text{ seconds}$.
   - **Sample Consistency**: Minimum 10 consecutive samples where $P(\text{Failure}) < 0.15$.
3. If any instability, packet loss, or CRC burst occurs during this window, $t_{recovery}$ and the sample counter are reset to zero.
4. Only upon fulfilling both criteria does the controller restore the OSPF cost from `100` back to `10`.
