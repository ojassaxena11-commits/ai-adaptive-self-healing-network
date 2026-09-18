# Architecture Specification: AI-Driven Adaptive Self-Healing Network

## 1. System Overview

The **AI-Driven Adaptive Self-Healing Network** is a closed-loop cyber-infrastructure system engineered to overcome the inherent convergence latency and packet loss of traditional interior gateway routing protocols (specifically OSPF). By continuously collecting multi-dimensional telemetry (RTT, jitter, packet loss, CRC alignment errors, interface counters, and link flaps), the system extracts time-series trend slopes and rolling instability metrics. 

A lightweight, explainable Machine Learning model predicts impending link degradation, while a Time-to-Failure (TTF) engine calculates the remaining operational horizon before failure. A confidence-gated decision engine evaluates candidate alternate paths against application-specific Quality of Service (QoS) constraints and preemptively updates Cisco OSPF link metrics before physical link failure occurs, achieving **zero downtime and 0% packet loss**.

---

## 2. High-Level Modular Decoupling

```text
+-------------------------------------------------------------------------------+
|                            CISCO NETWORK LAYER                                |
|        (Cisco Modeling Labs IOSv / IOSvL2 Virtual Topology or Simulation)      |
|               R1 (Source) -> SW1 (Ingress) <===> SW2 (Egress) -> R2 (Sink)   |
|                                     \             /                           |
|                                      v           ^                            |
|                                     SW3 (Backup)                              |
+-------------------------------------------------------------------------------+
                                      |
                       [Continuous Telemetry Stream]
                                      v
+-------------------------------------------------------------------------------+
|                         TELEMETRY INGESTION & PARSING                         |
|   - Real-time SSH / CML REST interface counters (`show interface counters`)   |
|   - ICMP Latency & Jitter Probes                                              |
|   - Standardized Schema: [RTT, Jitter, Loss, CRC, Errors, Flaps, Util, Cost]  |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                        TIME-SERIES FEATURE ENGINEERING                        |
|   - Configurable Sliding Windows: W in {5, 10, 20} samples                    |
|   - Ordinary Least Squares (OLS) Linear Slopes (m = dy/dt)                   |
|   - Rolling Mean & Standard Deviation                                         |
|   - Multi-Factor Composite Instability Index (0 - 100)                        |
+-------------------------------------------------------------------------------+
                                      |
                  +-------------------+-------------------+
                  |                                       |
                  v                                       v
+-----------------------------------+   +---------------------------------------+
|     FAILURE PREDICTION ENGINE     |   |      TIME-TO-FAILURE (TTF) ENGINE     |
| - Model: DecisionTreeClassifier   |   | - Physical Degradation Trajectory     |
| - Outputs: P(Failure) in [0, 1]   |   | - Dynamic OLS Rate Projection         |
| - Confidence Score C in [0, 1]    |   | - Horizon Estimate with Uncertainty   |
| - Explainable Indicator Extraction|   |   Bounds: [TTF_min, TTF_max] ms       |
+-----------------------------------+   +---------------------------------------+
                  \                                       /
                   +------------------+------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                    CONFIDENCE-GATED DECISION ENGINE                           |
|   - Risk Gating: P(Failure) >= 0.75                                           |
|   - Confidence Gate: Confidence >= 0.80 (Prevents false alarms & flap churn)  |
|   - Policy Arbiter: MONITOR | INCREASE_MONITORING | PREEMPTIVE_REROUTE       |
|   - Safety Guard: DRY_RUN execution interception                              |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                   TRAFFIC-AWARE QoS PATH EVALUATOR                            |
|   - Multi-Criteria Decision Analysis (MCDA) Path Penalty Scoring              |
|   - Dynamic Application Profiles:                                             |
|       * VOIP        : High sensitivity to jitter, packet loss & latency       |
|       * VIDEO       : Prioritizes bandwidth utilization & packet loss         |
|       * NORMAL_DATA : Best-effort, prioritizes hop count & link stability     |
|   - Real-time Candidate Ranking: Primary Path vs. Backup Path via SW3         |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                       CISCO AUTOMATION CONTROLLER                             |
|   - Netmiko SSH & CML REST API Driver (or Simulated IOS State Engine)         |
|   - Action: Preemptively increases Primary OSPF Cost: `ip ospf cost 10 -> 100`|
|   - OSPF Shortest Path First (SPF) automatically converges to Backup (Cost 40)|
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                 FEEDBACK & ANTI-FLAPPING HYSTERESIS ENGINE                    |
|   - Post-action classification: True Positive, False Positive, Recovery Succ  |
|   - Achieved Failure Lead Time Verification: T_fail - T_predict               |
|   - Route Flap Damping: 15-second / 10-healthy-sample stability timer         |
|   - Safe restoration of Primary OSPF metric (`100 -> 10`) upon recovery       |
+-------------------------------------------------------------------------------+
```

---

## 3. Data Pipeline & Interface Schemas

### 3.1 Telemetry Data Contract (`data/telemetry.csv`)
Each monitored link record adheres to this strict CSV schema:
- `timestamp`: ISO-8601 formatted datetime (`YYYY-MM-DD HH:MM:SS.mmm`)
- `device`: Hostname of reporting Cisco entity (e.g., `SW1`)
- `interface`: Physical or logical port ID (e.g., `GigabitEthernet0/1`)
- `path_id`: Logical path identifier (`PATH_PRIMARY` or `PATH_BACKUP`)
- `rtt`: Round-Trip Latency in milliseconds
- `jitter`: Variation in packet transit delay in milliseconds
- `packet_loss`: Percentage of dropped probe frames ($0.0 - 100.0\%$)
- `crc_errors`: Cumulative hardware Cyclic Redundancy Check frame errors
- `interface_errors`: Cumulative hardware transmit/receive errors
- `interface_flaps`: Cumulative link state transitions (up/down transitions)
- `utilization`: Bandwidth utilization percentage ($0.0 - 100.0\%$)
- `link_status`: Operational interface status (`UP` or `DOWN`)
- `ospf_cost`: Current configured interface OSPF metric
- `telemetry_source`: Origin label (`REAL_CML` or `SIMULATION`)

### 3.2 Engineered Feature Vector
The Feature Engine ingests the sliding window history $H = [t_{-W}, \dots, t_0]$ and constructs a 25-dimensional normalized vector passed to the prediction model:
$$\mathbf{X} = [\text{RTT}_{curr}, \mu_5(\text{RTT}), \sigma_5(\text{RTT}), \text{Slope}_5(\text{RTT}), \mu_{10}(\text{RTT}), \text{Slope}_{10}(\text{RTT}), \dots, \text{InstabilityScore}]$$

---

## 4. Cisco OSPF Rerouting Mechanics

Under standard OSPF (Area 0):
- **Primary Path** (`R1 -> SW1 -> SW2 -> R2`): Total Cost = $10 + 10 + 10 = \mathbf{30}$
- **Backup Path** (`R1 -> SW1 -> SW3 -> SW2 -> R2`): Total Cost = $10 + 10 + 10 + 10 = \mathbf{40}$

When the Decision Engine triggers a `PREEMPTIVE_REROUTE`:
1. The Cisco Controller logs into `SW1` via SSH.
2. Dispatches commands:
   ```text
   interface GigabitEthernet0/1
    ip ospf cost 100
   end
   ```
3. The new total cost for the primary path becomes $10 + 100 + 10 = \mathbf{120}$.
4. OSPF immediately calculates that the backup path via `SW3` (Cost $\mathbf{40}$) is the new Shortest Path First (SPF) tree.
5. Ingress traffic is diverted onto the backup link **before** `GigabitEthernet0/1` experiences physical failure.
