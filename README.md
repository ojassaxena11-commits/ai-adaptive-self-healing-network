# AI-Driven Adaptive Self-Healing Network

> **A Research-Grade Cyber-Infrastructure Prototype for Confidence-Aware, Predictive Network Rerouting, OSPF Self-Healing, and Multi-Dimensional Telemetry Analytics.**

---

## 1. Executive Summary & Problem Statement

Modern packet-switched networks rely on interior gateway protocols such as **OSPF** to maintain loop-free shortest paths across distributed topologies. However, OSPF is fundamentally **reactive**: it detects link failures only after physical link drop interrupts or after the expiration of keepalive Hello/Dead timers (typically 4–40 seconds). During this blackout window, high volumes of inflight packets are dropped, disrupting real-time applications like Voice over IP (VoIP), financial transactions, and streaming media.

This project introduces an **Adaptive Risk-Aware AI-Based Self-Healing Network**. Rather than waiting for link collapse, the system continuously ingests multi-dimensional telemetry (RTT, jitter, packet loss, CRC alignment errors, interface counters, and flaps), derives temporal rate-of-change trend slopes, predicts impending failure risk using explainable machine learning, projects time-to-failure (TTF), and **preemptively manipulates Cisco OSPF link metrics** to divert traffic onto healthy backup paths with **zero packet loss and zero downtime**.

---

## 2. Key System Capabilities

- **Multi-Dimensional Telemetry Telemetry**: Continuous streaming of RTT, jitter, loss, CRC errors, interface flaps, and utilization.
- **Trend-Velocity Feature Engineering**: Sliding-window ordinary least-squares linear slopes ($dy/dt$) capturing degradation acceleration.
- **Explainable Failure Prediction**: Lightweight `DecisionTreeClassifier` with feature attribution and confidence assessment.
- **Time-to-Failure (TTF) Estimation**: Dynamic physical trajectory extrapolation and regression providing lead-time intervals ($[T_{min}, T_{max}] \text{ ms}$).
- **Confidence-Gated Decision Engine**: Rejects uncertain predictions ($C < 80\%$) to eliminate route flapping from transient noise.
- **Traffic-Aware QoS Path Evaluation**: Multi-factor objective penalty scoring dynamically weighted for **VOIP**, **VIDEO**, or **NORMAL_DATA**.
- **Automated Cisco OSPF Preemption**: Modifies Cisco interface metric (`ip ospf cost 10 -> 100`) to trigger seamless Dijkstra SPF recalculation before physical failure.
- **Anti-Flapping Route Restoration Hysteresis**: 15-second / 10-healthy-sample observation timer before reverting to primary link.
- **Dual Operating Modes**:
  - `MODE=CML`: Live integration with Cisco Modeling Labs via CML REST API and Netmiko/SSH to real IOSv/IOSvL2 nodes.
  - `MODE=SIMULATION`: High-fidelity in-memory network state engine for deterministic offline experimentation and live demo.
- **Professional Streamlit NOC Dashboard**: Real-time topology diagrams, telemetry charts, AI risk gauges, and audit event logs.

---

## 3. High-Level Architecture

```text
               +-------------------------------------------+
               |     CISCO TOPOLOGY (CML or Simulation)    |
               | R1 (Source) -> SW1 (Core) ===> SW2 -> R2  |
               |                       \       /           |
               |                        v     ^            |
               |                       SW3 (Backup)        |
               +---------------------+---------------------+
                                     |
                         [Live Telemetry Stream]
                                     v
                       +---------------------------+
                       |    Telemetry Collector    |
                       +-------------+-------------+
                                     v
                       +---------------------------+
                       |    Feature Engineering    |
                       |  (Rolling Window Slopes)  |
                       +-------------+-------------+
                                     v
                  +------------------+------------------+
                  v                                     v
     +-------------------------+           +-------------------------+
     | Failure Risk Prediction |           | Time-to-Failure Engine  |
     | (DecisionTreeClassifier)|           | (Trajectory Extrapol.)  |
     +------------+------------+           +------------+------------+
                  \                                     /
                   +-----------------+-----------------+
                                     v
                       +---------------------------+
                       |  Decision Engine & Gating |
                       | (Risk >= 0.75, Conf >= 80%)|
                       +-------------+-------------+
                                     v
                       +---------------------------+
                       | Traffic QoS Path Evaluator|
                       | (VOIP, Video, Data Matrix)|
                       +-------------+-------------+
                                     v
                       +---------------------------+
                       | Cisco Network Controller  |
                       |  `ip ospf cost 10 -> 100` |
                       +-------------+-------------+
                                     v
                       +---------------------------+
                       |  Feedback & Anti-Flapping |
                       |    Hysteresis Engine      |
                       +---------------------------+
```

---

## 4. Technology Stack

- **Network Environment**: Cisco Modeling Labs (CML 2.x), Cisco IOSv, Cisco IOSvL2, OSPF Area 0, IPv4.
- **Programming & ML**: Python 3.13, `pandas`, `numpy`, `scikit-learn`, `matplotlib`, `joblib`.
- **Network Automation**: `netmiko`, `paramiko`, `requests` (CML REST API v2/v3).
- **Visualization & Web App**: Streamlit, Altair.
- **Testing & Tooling**: Python `unittest`, Git, PyYAML.

---

## 5. Quickstart & Installation

### Step 5.1: Clone and Install Dependencies
```powershell
git clone <repo-url>
cd "computer networks project"

# Install dependencies
pip install -r requirements.txt
```

### Step 5.2: Configure Environment
Copy `.env.example` to `.env` (already configured with default simulation settings):
```powershell
copy .env.example .env
```

---

## 6. Execution Commands Guide

### A. Run End-to-End Automated Live Demonstration
Executes all 10 phases of the self-healing cycle (Discovery -> Telemetry -> Degradation -> Feature Slopes -> AI Risk -> TTF -> QoS Path Selection -> Cisco Preemption -> Link Collapse -> Hysteresis Recovery):
```powershell
python demo.py
```

### B. Train the Machine Learning & TTF Models
Generates 5,000+ multi-scenario time-series samples, trains `DecisionTreeClassifier` (primary explainable model), benchmarks against `RandomForest` and `LogisticRegression`, trains the TTF regressor, and saves serialized models to `models/`:
```powershell
python train.py
```

### C. Run the Experimental Benchmarks (Reactive vs. Proactive)
```powershell
# 1. Run traditional reactive OSPF baseline experiment
python src/experiments/reactive_experiment.py

# 2. Run AI proactive self-healing experiment
python src/experiments/proactive_experiment.py

# 3. Generate comparative markdown reports and plots
python src/experiments/compare_experiments.py
```

### D. Launch the Professional Streamlit NOC Dashboard
```powershell
streamlit run src/dashboard/dashboard.py
```
*Access the interactive monitoring dashboard in your browser at `http://localhost:8501`.*

### E. Run Live Controller CLI
```powershell
# Run monitoring in simulation mode for VoIP traffic
python main.py --mode simulation --traffic-class voip --scenario 4

# Run with DRY_RUN safety mode enabled
python main.py --mode simulation --dry-run

# Run in live CML mode (requires CML cluster)
python main.py --mode cml --traffic-class data
```

### F. Run the Automated Unit & Integration Test Suite
```powershell
python -m unittest discover tests -v
```

---

## 7. Experimental Benchmark Results

| Metric | Traditional Reactive OSPF | AI-Driven Adaptive Self-Healing | Operational Improvement |
| :--- | :--- | :--- | :--- |
| **Failure Detection** | Dead interval timeout (Reactive) | ML trend regression (Proactive) | **Predictive Preemption** |
| **Action Lead Time** | 0 ms (after blackout) | **4,500 ms** (before blackout) | **+4,500 ms early warning** |
| **Convergence Blackout** | **5,000 ms** blackout | **0 ms** (instantaneous) | **100% Downtime Elimination** |
| **Overall Packet Loss** | **20.0%** (50 dropped packets) | **0.8%** (2 drift packets) | **96.0% Packet Loss Reduction** |
| **Peak Latency Spike** | **999 ms** (packet loss timeout)| **18.6 ms** (stable backup) | **98.1% Latency Stabilization** |
| **Route Flap Damping** | None (oscillation vulnerability) | 15s Hysteresis Stability Timer | **Guaranteed Anti-Flapping** |
| **QoS Profile Adaptability** | Metric-blind | VOIP, Video, Best-effort Data | **Application-Aware Routing** |

---

## 8. Cisco Modeling Labs (CML) Deployment

For deploying onto physical or virtual Cisco Modeling Labs:
1. Review the step-by-step setup guide: [`cml/README_CML_SETUP.md`](cml/README_CML_SETUP.md).
2. Import the complete lab definition into CML: [`cml/topology.yaml`](cml/topology.yaml).
3. Apply the individual Cisco startup configurations located in [`cml/configs/`](cml/configs/):
   - `R1.cfg`: Source Gateway
   - `SW1.cfg`: Distribution Ingress Core (AI Control Target)
   - `SW2.cfg`: Distribution Egress Core
   - `SW3.cfg`: Redundant Transit Switch
   - `R2.cfg`: Destination Gateway

---

## 9. Comprehensive Documentation Index

- **System Architecture**: [`docs/architecture.md`](docs/architecture.md)
- **Technical Implementation & Internals**: [`docs/implementation.md`](docs/implementation.md)
- **Experimental Methodology & Scenarios**: [`docs/experiments.md`](docs/experiments.md)
- **Engineering Limitations**: [`docs/limitations.md`](docs/limitations.md)
- **Comprehensive Viva Voce Q&A Guide**: [`docs/viva_questions.md`](docs/viva_questions.md)
- **Patent-Oriented Invention Notes**: [`docs/invention_notes.md`](docs/invention_notes.md)

---

## 10. Project Team Contributions

| Member Name | Role & Core Responsibilities | Specific Modules Owned |
| :--- | :--- | :--- |
| **Member 1** | **Network Architecture & CML Automation** | Cisco topology design (`topology.yaml`), OSPF routing, Netmiko SSH controller (`cisco_controller.py`), CLI parser (`parser.py`). |
| **Member 2** | **Machine Learning & Telemetry Data Science** | Synthetic telemetry generator (`simulator.py`), feature engineering slopes (`feature_engine.py`), ML Decision Tree & TTF training (`train.py`, `failure_predictor.py`, `ttf_predictor.py`). |
| **Member 3** | **Decision Logic, DevOps & Dashboard Engineering** | Confidence-gated decision engine (`decision_engine.py`), QoS path evaluator (`path_evaluator.py`), Streamlit NOC dashboard (`dashboard.py`), test suite (`tests/`). |
