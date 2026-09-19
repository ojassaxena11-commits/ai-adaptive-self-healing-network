# AI-Driven Adaptive Self-Healing Network

> **A Research-Grade Cyber-Infrastructure Prototype for Confidence-Aware, Predictive Network Rerouting, OSPF Self-Healing, and Multi-Dimensional Telemetry Analytics across Cisco Modeling Labs (CML) and High-Fidelity Simulation.**

---

## 1. Executive Summary & Problem Statement

Modern packet-switched computer networks rely on interior gateway protocols such as **OSPF** to maintain loop-free shortest paths across distributed topologies. However, OSPF is fundamentally **reactive**: it detects link failures only after physical link drop interrupts or after the expiration of keepalive Hello/Dead timers (typically 4–40 seconds). During this blackout window, high volumes of in-flight packets are dropped, severely disrupting mission-critical applications like Voice over IP (VoIP), financial transactions, and streaming media.

This project introduces an **Adaptive Risk-Aware AI-Based Self-Healing Network**. Rather than waiting for catastrophic link collapse, the system continuously monitors multi-dimensional telemetry (RTT, jitter, packet loss, CRC alignment errors, input/output errors, and interface flaps), derives temporal rate-of-change trend slopes, predicts impending failure risk using explainable machine learning, projects time-to-failure (TTF), and **preemptively manipulates Cisco OSPF link metrics** to divert traffic onto healthy backup paths with **zero packet loss and zero downtime**.

---

## 2. Key System Capabilities

- **ONE Unified Dashboard with Environment Selector**:
  - `[ SIMULATION ]`: High-fidelity deterministic mathematical state engine for instant, offline execution without external software.
  - `[ CML ]`: Direct integration with Cisco Modeling Labs 2.x virtual topology via REST API (Port 443) and Netmiko SSH (Port 22).
- **Multi-Dimensional Telemetry Streaming**: Real-time polling and normalization of RTT, jitter, loss, CRC errors, input/output errors, interface flaps, and link utilization.
- **Trend-Velocity Feature Engineering**: Sliding-window ordinary least-squares (OLS) linear slopes ($dy/dt$) capturing degradation acceleration.
- **Explainable Failure Prediction**: Lightweight `DecisionTreeClassifier` with feature attribution indicators and confidence estimation.
- **Time-to-Failure (TTF) Estimation**: Dynamic physical trajectory extrapolation providing operational lead-time intervals ($[T_{min}, T_{max}] \text{ ms}$).
- **Confidence-Gated Decision Engine**: Rejects uncertain predictions ($C < 80\%$) to eliminate route flapping from transient noise.
- **Traffic-Aware QoS Path Evaluation**: Multi-factor objective penalty scoring dynamically weighted for **VOIP**, **VIDEO**, or **NORMAL_DATA**.
- **Automated Cisco OSPF Preemption**: Modifies Cisco interface metric (`ip ospf cost 10 -> 100`) to trigger seamless Dijkstra SPF recalculation before physical failure.
- **Live Routing Table Verification**: Inspects Cisco OSPF routing tables (`show ip route ospf`) to confirm traffic migration to the backup transit path.
- **Anti-Flapping Route Restoration Hysteresis**: 15-second / 10-consecutive-healthy-sample observation timer before reverting to primary link.
- **Safe DRY_RUN Mode**: Audits and displays Cisco commands without mutating device configurations.
- **Controlled Failure Injection**: Safe GUI failure mechanisms with explicit confirmation toggles to prevent accidental topology destruction.

---

## 3. High-Level Architecture

```text
Streamlit GUI
    ↓
Environment Selector
    ↓
 ┌───────────────┬───────────────┐
 │               │
SIMULATION       CML
 │               │
NetworkSimulator Cisco CML
 │               │
 └───────┬───────┘
         ↓
Telemetry
         ↓
Feature Engineering
         ↓
AI Failure Prediction
         ↓
TTF Prediction
         ↓
Risk + Confidence
         ↓
Decision Engine
         ↓
QoS Path Evaluator
         ↓
Cisco Routing Controller
         ↓
Network
         ↓
Feedback Engine
```

---

## 4. Cisco Network Topology

The project models a redundant Cisco enterprise network running OSPF Area 0:

```text
                 [ R1: Source Gateway ]
                           |
                           v
              +-------------------------+
              | SW1: Core Ingress Switch|
              +-------------------------+
                     /           \
   (Primary: Cost 10) /             \ (Backup: Cost 10)
                   /               \
                  v                 v
  +-------------------------+     +-------------------------+
  | SW2: Core Egress Switch | <---| SW3: Backup Transit Switch|
  +-------------------------+     +-------------------------+
               |
               v
     [ R2: Destination Gateway ]
```

- **Primary Path** (`R1 → SW1 → SW2 → R2`): Total Baseline Cost = $10 + 10 + 10 = \mathbf{30}$ (**ACTIVE**)
- **Backup Path** (`R1 → SW1 → SW3 → SW2 → R2`): Total Baseline Cost = $10 + 10 + 10 + 10 = \mathbf{40}$ (**STANDBY**)
- **Self-Healing Action**: When degradation is detected, the AI increases `SW1:Gi0/1` cost to **100**. The Primary Path cost becomes $120$, causing OSPF to immediately select the Backup Path ($40$) **before the physical link fails**.

---

## 5. Quickstart & Installation

### Option 1: One-Click Launcher (Windows)
Double-click **`START_PROJECT.bat`** in the repository root. This script automatically:
1. Verifies Python 3.10+ installation.
2. Creates and activates a virtual environment (`.venv`).
3. Installs all dependencies from `requirements.txt`.
4. Starts the Streamlit NOC Dashboard at `http://localhost:8501`.

### Option 2: Manual Terminal Setup
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the unified dashboard
streamlit run app.py
```

---

## 6. Cisco Modeling Labs (CML) Setup

To connect the application to a live Cisco Modeling Labs topology:

1. **Deploy CML**: Follow the detailed guide in [cml/README_CML_SETUP.md](cml/README_CML_SETUP.md).
2. **Import Topology**: In CML, click **Import** and select `cml/topology.yaml`.
3. **Configure Devices**: Apply the startup configurations from `cml/configs/` (`R1.cfg`, `SW1.cfg`, `SW2.cfg`, `SW3.cfg`, `R2.cfg`).
4. **Configure Credentials in `.env`**:
   ```ini
   # Operational Environment
   MODE=SIMULATION

   # CML Controller REST API
   CML_HOST=192.168.1.100
   CML_PORT=443
   CML_USER=admin
   CML_PASS=YourPasswordHere
   CML_LAB_ID=lab-adaptive-mesh
   CML_VERIFY_SSL=false

   # Cisco Device SSH Credentials
   CISCO_USERNAME=cisco
   CISCO_PASSWORD=cisco
   CISCO_ENABLE_SECRET=cisco

   # Dry Run Safety Mode
   DRY_RUN=false
   ```
   > **SECURITY NOTE**: Never hard-code credentials or commit `.env` to git. `.env` is listed in `.gitignore`.

---

## 7. Running the Test Suite

Execute the comprehensive test suite covering CML REST client, output parsing, telemetry normalization, dry-run safety, environment switching, and decision logic:

```powershell
python -m unittest discover tests -v
```

All 33 unit and integration tests should pass with 0 failures and 0 errors:
```text
Ran 33 tests in 4.480s
OK
```

---

## 8. Teacher & Evaluator Demonstration Guide

### Presentation Flow A: SIMULATION Mode Demonstration (Offline & Fast)
1. Open dashboard at `http://localhost:8501`.
2. In the sidebar, select **Environment: `[ SIMULATION ]`**.
3. Set **Traffic Class** to `VOIP`.
4. Select **Scenario: `Scenario 4: Failure with Backup Preemption`**.
5. Click **▶ Step Once** sequentially:
   - Observe baseline metrics at Step 1–2: RTT ~11ms, Jitter ~1.5ms, Loss 0%, Risk < 10%.
   - At Step 3–4: Observe accelerating jitter and CRC errors. AI switches to `WARNING` -> `HIGH_RISK` ($P \ge 75\%$, Confidence $\ge 80\%$, TTF ~4.2s).
   - **Decision Engine triggers `PREEMPTIVE_REROUTE`**.
   - OSPF cost on `SW1:Gi0/1` updates from 10 to 100. Traffic migrates to `R1 → SW1 → SW3 → SW2 → R2`.
   - At Step 5: Primary link physically collapses (`DOWN`). Point out to the evaluator that active traffic is already safely on the backup path with **0.0% packet loss**!
6. Click **`▶ RUN FULL SELF-HEALING DEMO`** to watch the automated 8-phase demonstration with live progress and lead time reporting.
7. Click **`📊 RUN REACTIVE VS PROACTIVE BENCHMARK`** to display the comparative graphs proving **96% packet loss reduction** and **100% convergence downtime elimination**.

### Presentation Flow B: CML Live Mode Demonstration (Cisco Hardware Virtualization)
1. In the sidebar, select **Environment: `[ CML ]`**.
2. Click **`🔌 Verify CML Connection`**. Observe connection status transition to **`CML CONNECTED ✓`** with node diagnostics.
3. Click **`📡 Collect Telemetry`** to poll live interface counters and ICMP ping probes from Cisco switches.
4. Click **`🧠 Run AI Prediction`** and **`🎯 Evaluate Backup`** to run ML inference and QoS path ranking on live data.
5. Click **`⚡ Execute Reroute`** to dispatch Cisco CLI configuration (`ip ospf cost 100`).
   - If `DRY_RUN` is enabled, show the exact Cisco commands audited in the GUI.
   - If `DRY_RUN` is disabled, observe live execution on the Cisco switch.
6. Click **`🔍 Verify Routing`** to inspect the Cisco routing table and confirm **`Traffic Migration: SUCCESS ✓`**.
7. Open **💥 Controlled Failure Injection**, check the safety confirmation toggle, and demonstrate graceful link shutdown and restoration.

---

## 9. Documentation Index

- [Architecture Specification](docs/architecture.md): Complete component and data flow specifications.
- [Implementation Details](docs/implementation.md): Technical deep-dive into classes, methods, and algorithms.
- [Experimental Methodology & Benchmarks](docs/experiments.md): Multi-scenario testbed and comparative results.
- [CML Deployment & Setup Guide](cml/README_CML_SETUP.md): Step-by-step virtualization and lab deployment guide.
