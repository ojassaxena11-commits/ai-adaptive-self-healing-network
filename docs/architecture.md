# System Architecture: AI-Driven Adaptive Self-Healing Network

## 1. Executive Architectural Overview

The **AI-Driven Adaptive Self-Healing Network** is an enterprise-grade autonomous networking system designed to overcome the fundamental limitation of interior gateway routing protocols (specifically OSPF): **reactive failure recovery**. 

Traditional OSPF protocols detect failures only after physical link down interrupts or dead-timer expirations (typically 4–40 seconds), causing packet blackouts. This architecture introduces a **closed-loop predictive control plane** that:
1. Gathers multi-dimensional telemetry (RTT, jitter, packet loss, CRC alignment errors, input/output errors, and interface flaps).
2. Extracts rolling-window rate-of-change trend slopes.
3. Predicts impending link failure and estimates remaining Time-to-Failure (TTF).
4. Evaluates alternate candidate paths against traffic-specific Quality of Service (QoS) constraints.
5. Employs a confidence gate ($C \ge 80\%$) and risk threshold ($P \ge 0.75$) to prevent flapping.
6. Preemptively increases the OSPF cost on the degrading link (`ip ospf cost 10 -> 100`) before physical collapse.
7. Verifies OSPF routing table convergence to guarantee zero packet loss and zero downtime.
8. Enforces anti-flapping hysteresis before restoring traffic to a recovered primary link.

---

## 2. End-to-End System Architecture

The project features **ONE unified Streamlit GUI** supporting two selectable environments: **SIMULATION** (high-fidelity in-memory network state engine) and **CML** (live Cisco Modeling Labs 2.x virtual topology).

```text
                     +---------------------------------------+
                     |             STREAMLIT GUI             |
                     |       (Unified NOC Dashboard)         |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |         ENVIRONMENT SELECTOR          |
                     |         [ SIMULATION | CML ]          |
                     +---------+-------------------+---------+
                               |                   |
            +------------------+                   +------------------+
            |                                                         |
            v                                                         v
+-------------------------------+                         +-------------------------------+
|        SIMULATION MODE        |                         |            CML MODE           |
|     (Deterministic State)     |                         |     (Physical Virtualization) |
|   - NetworkSimulator Engine   |                         |   - Cisco Modeling Labs 2.x   |
|   - 8 Operational Scenarios   |                         |   - CML REST API (Port 443)   |
|   - Step-by-Step Evolution    |                         |   - Netmiko SSH (Port 22)     |
+---------------+---------------+                         +---------------+---------------+
                |                                                         |
                +-----------------------+---------------------------------+
                                        |
                                        v
                     +---------------------------------------+
                     |          TELEMETRY COLLECTOR          |
                     |   (Normalized Heterogeneous Stream)   |
                     |   RTT, Jitter, Loss, CRC, In/Out Errs |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |       FEATURE ENGINEERING ENGINE      |
                     |  - Rolling Ordinary Least Squares     |
                     |  - Rate-of-Change Slopes (m = dy/dt)  |
                     |  - Multi-Factor Instability Index     |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |       AI FAILURE PREDICTION ENGINE    |
                     |  - Explainable DecisionTreeClassifier |
                     |  - Multi-Class Probabilities & Risk   |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |     TIME-TO-FAILURE (TTF) ENGINE      |
                     |  - Dynamic Physical Trajectory Model  |
                     |  - Horizon Interval: [TTF_min, max]   |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |     RISK + CONFIDENCE GATE ARBITER    |
                     |  - Risk Threshold >= 0.75             |
                     |  - Confidence Gate >= 0.80            |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |            DECISION ENGINE            |
                     |  MONITOR | INCREASE_MON | REROUTE     |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |        QoS-AWARE PATH EVALUATOR       |
                     |  - Multi-Criteria Decision Analysis   |
                     |  - VOIP, VIDEO, NORMAL_DATA Profiles  |
                     |  - Candidate Ranking (Primary vs SW3) |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |       CISCO ROUTING CONTROLLER        |
                     |  - Safe DRY_RUN Command Auditing      |
                     |  - Live Cisco IOS CLI Metric Mutation |
                     |    `interface Gi0/1 -> cost 100`      |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |       NETWORK ROUTING CONVERGENCE     |
                     |  - OSPF Dijkstra SPF Recalculation    |
                     |  - Routing Table Verification         |
                     |  - Traffic Migration: SUCCESS         |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |        FEEDBACK & HYSTERESIS ENGINE   |
                     |  - Prediction Confusion Classification|
                     |  - Measured Lead Time Tracking        |
                     |  - 15s Flap-Damping Recovery Timer    |
                     +---------------------------------------+
```

---

## 3. Core Component Subsystems

### 3.1 Environment Selector & Telemetry Normalization
The `TelemetryCollector` acts as a unified abstraction layer. Regardless of whether data originates from `NetworkSimulator` or live Cisco IOS devices via `CiscoController`, records are normalized into a common dictionary schema:
- `timestamp`: Polling cycle ISO timestamp
- `device`: Reporting Cisco switch hostname (e.g. `SW1`)
- `interface`: Reporting port (e.g. `GigabitEthernet0/1`)
- `path_id`: Logical path identifier (`PATH_PRIMARY` or `PATH_BACKUP`)
- `rtt`: Round-Trip Time in milliseconds
- `jitter`: Variation in delay in milliseconds
- `packet_loss`: Percentage of dropped packets ($0.0 - 100.0\%$)
- `crc_errors`: Frame Check Sequence / CRC hardware alignment errors
- `input_errors`: Ingress queue and malformed frame counters
- `output_errors`: Egress buffer drop counters
- `interface_errors`: Composite error counter
- `interface_flaps`: Cumulative link carrier transitions
- `utilization`: Bandwidth consumption percentage ($0.0 - 100.0\%$)
- `link_status`: Physical port administrative and operational state (`UP` / `DOWN`)
- `ospf_cost`: Active OSPF metric assigned to the interface
- `telemetry_source`: Indicator string (`SIMULATION` or `CML`)

### 3.2 Feature Engineering Layer (`src/features/feature_engine.py`)
Raw telemetry samples are stored in a rolling window buffer ($W = 5$ samples). The `FeatureEngine` derives 14 temporal features:
- Rolling means and standard deviations for RTT, Jitter, and Packet Loss.
- First-order trend slopes ($dy/dt$) using Ordinary Least Squares (OLS):
  $$\text{Slope} = \frac{\sum_{k=0}^{W-1} (k - \bar{x})(y_k - \bar{y})}{\sum_{k=0}^{W-1} (k - \bar{x})^2}$$
- CRC error delta ($\Delta \text{CRC}_5$).
- Instability score ($0.0 - 100.0$), aggregating multidimensional anomalies into a single composite metric.

### 3.3 AI Prediction & TTF Estimation (`src/prediction/`)
- **Failure Predictor**: A scikit-learn `DecisionTreeClassifier` trained on simulated physical degradation telemetry. It classifies the link state into `HEALTHY`, `WARNING`, or `HIGH_RISK`, outputs class probabilities, and isolates contributing indicators (e.g., accelerating jitter slope, cumulative CRC accumulation) for full explainability.
- **TTF Predictor**: Models physical failure trajectory by projecting loss degradation velocity toward a critical operational threshold ($L_{crit} = 15.0\%$), damped by the composite instability index to provide an estimated lead time interval $[T_{min}, T_{max}]$.

### 3.4 Confidence-Gated Decision Engine (`src/decision/decision_engine.py`)
To prevent dangerous route oscillations caused by transient burst noise, the decision engine requires:
1. **Risk Threshold**: Impending failure probability $P \ge 0.75$.
2. **Confidence Threshold**: Classification confidence $C \ge 0.80$.
3. **Backup Quality Check**: The candidate backup path must not be congested or degraded.
If all gates pass, `PREEMPTIVE_REROUTE` is triggered. Otherwise, the system safely falls back to `INCREASE_MONITORING` or `MONITOR`.

### 3.5 Traffic-Aware QoS Path Evaluator (`src/routing/path_evaluator.py`)
Candidate paths are dynamically scored based on application profiles:
- **VOIP**: Heavy penalties on latency (0.35) and packet loss (0.40).
- **VIDEO**: Heavy penalties on bandwidth utilization (0.35) and loss (0.25).
- **NORMAL_DATA**: Balanced weighting across hops, loss, latency, and utilization.

### 3.6 Cisco Network Controller (`src/routing/cisco_controller.py`)
- **Dual Connection Planes**: Manages CML REST API (JWT bearer authentication, node lifecycle queries) and Netmiko SSH sessions.
- **Safe DRY_RUN Mode**: When enabled, generates and logs exact Cisco configuration commands without mutating device configurations.
- **Live Routing Mutation**: Executes `interface GigabitEthernet0/1` -> `ip ospf cost 100` -> `end` on the ingress core switch.
- **Routing Table Verification**: Executes `show ip route ospf` and verifies whether traffic to destination subnets has migrated to the backup transit path.
- **Controlled Failure Injection**: Safely shuts down or enables interfaces with confirmation checks.

### 3.7 Feedback & Anti-Flapping Hysteresis Engine (`src/feedback/feedback_engine.py`)
- **Outcome Classification**: Evaluates decisions against post-event ground truth (`TRUE_POSITIVE`, `FALSE_POSITIVE`, `TRUE_NEGATIVE`, `FALSE_NEGATIVE`).
- **Lead Time Verification**: Compares predicted TTF against actual elapsed time between rerouting and link drop.
- **Flap Damping Hysteresis**: Prevents immediate route reverting upon brief link recovery by enforcing a 15-second / 10-consecutive-healthy-sample observation window before restoring OSPF cost to 10.
