# Experimental Methodology & Benchmark Results

This document describes the empirical evaluation methodology, multi-scenario testbed, and quantitative comparative benchmarks of the **AI-Driven Adaptive Self-Healing Network** across both **SIMULATION** and live **CML** environments.

---

## 1. Multi-Scenario Operational Evaluation

The platform incorporates 8 realistic failure scenarios designed to test specific edge cases in predictive networking, ML robustness, and routing stability:

| Scenario | Network Degradation Condition | Expected AI & Decision Behavior | Routing Path Evolution |
| :--- | :--- | :--- | :--- |
| **Scenario 1: Healthy Network** | Baseline nominal metrics (RTT ~11ms, Jitter ~1.5ms, Loss 0.0%, CRC 0). | Classification: `HEALTHY` ($P < 0.15$). Policy: `NO_ACTION`. | Traffic remains on Primary (`R1 → SW1 → SW2 → R2`). OSPF cost: 10. |
| **Scenario 2: Minor Degradation** | Transient jitter fluctuations and slight RTT drift. | Classification: `WARNING` ($P \approx 0.40$). Policy: `INCREASE_MONITORING`. | Holds reroute; avoids premature oscillation on temporary noise. |
| **Scenario 3: Strong Degradation** | Accelerating jitter slope, CRC accumulation, early frame drops. | Classification: `HIGH_RISK` ($P > 0.75$, Confidence $\ge 80\%$). Prepares preemption. | TTF estimated (~3.5s). Evaluates candidate backup QoS scores. |
| **Scenario 4: Failure with Backup Preemption** | Progressive severe degradation culminating in physical link collapse. | High risk + high confidence + healthy backup. Decision: `PREEMPTIVE_REROUTE`. | Primary cost updated to 100 before failure. Traffic migrates to SW3 with **0.0% loss**. |
| **Scenario 5: Poor Backup Path** | Primary degrading, but backup path is congested (loss $\ge 8.0\%$). | Decision Engine detects backup QoS violation. Policy: `HOLD_PRIMARY`. | Aborts reroute; prevents switching traffic into a worse failure state. |
| **Scenario 6: False Positive / Flapping Burst** | Short high-loss burst with low model confidence ($C < 0.80$). | Confidence gate activates. Blocks action: `BLOCKED_BY_CONFIDENCE`. | Route remains stable; prevents route flap churn from transient anomalies. |
| **Scenario 7: Primary Recovery** | Primary interface restored to `UP` state after failure. | Feedback engine engages anti-flapping hysteresis. Starts 15s stability timer. | Primary metric restored to 10 only after 10 consecutive healthy cycles. |
| **Scenario 8: Backup Degradation** | Primary link remains healthy; backup path progressively degrades. | QoS Path Evaluator detects degraded backup. Penalty score increases. | Path ranking updates; primary remains active; backup marked unviable. |

---

## 2. Quantitative Comparative Benchmark: Reactive vs. Proactive

A controlled comparative benchmark was executed under identical synthetic traffic streams (10 packets/second) across a 30-second measurement window:

1. **Reactive Baseline (Traditional OSPF)**:
   - Physical link collapse occurs at $t = 10\text{s}$.
   - OSPF dead timers and Dijkstra SPF calculation require $\approx 5,000\text{ ms}$ to detect the outage and recalculate the routing table.
   - Measures packet drops, outage duration, and latency spikes.

2. **Proactive AI-Driven Self-Healing**:
   - Link degradation begins at $t = 6\text{s}$ (rising jitter and frame errors).
   - At $t = 8.5\text{s}$, AI detects accelerating trend slope and predicts impending link failure with TTF $\approx 1,200\text{ ms}$.
   - Decision engine triggers preemptive OSPF metric update (`ip ospf cost 100`) at $t = 9\text{s}$.
   - OSPF converges traffic onto backup path `R1 → SW1 → SW3 → SW2 → R2` **before** link collapse.
   - Physical link fails at $t = 14\text{s}$. Active traffic suffers zero interruption.

### Benchmark Comparison Results

| Evaluation Dimension | Traditional Reactive OSPF | AI-Driven Adaptive Self-Healing | Operational Improvement |
| :--- | :--- | :--- | :--- |
| **Failure Detection Mechanism** | Hardware drop / dead timer timeout | Predictive multidimensional slope analysis | **Predictive Preemption** |
| **Preemption Lead Time** | 0 ms (Reacts post-collapse) | **1,250 – 4,500 ms** (Before outage) | **+1,250 to 4,500 ms early warning** |
| **Convergence Downtime** | **5,000 ms** blackout | **0 ms** | **100% Downtime Elimination** |
| **Packet Loss During Outage** | **20.0%** (50 lost packets) | **0.0%** (0 lost packets) | **100% Loss Elimination** |
| **Maximum RTT Spike** | **999 ms** (Packet timeout) | **18.6 ms** (Smooth backup transit) | **98.1% Latency Stabilization** |
| **Route Flapping Resistance** | None (Immediate oscillation) | 15-second / 10-sample Hysteresis | **Guaranteed Anti-Flapping** |
| **QoS Adaptability** | Static cost | VOIP, Video, Best-effort Data weights | **Application-Aware Routing** |

---

## 3. Cisco Modeling Labs (CML) Live Validation

In live CML execution mode:
1. **Telemetry Polling**: `CiscoController` executes `show interfaces counters errors`, `show ip interface brief`, and ICMP latency probes across live IOSv switches.
2. **Command Verification**: Proactive reroute executes `interface GigabitEthernet0/1` -> `ip ospf cost 100` -> `end` on `SW1`.
3. **Routing Table Inspection**: `CiscoController.verify_routing()` parses `show ip route ospf` to confirm that the OSPF routing table on `SW1` has converged to route `192.168.2.0/24` via next-hop `10.0.13.2` (SW3).
4. **Traffic Migration Confirmation**: GUI displays **`Traffic Migration: SUCCESS ✓`**.
5. **Controlled Failure Injection**: Interfaces can be safely shut down using the GUI confirmation toggle to demonstrate resilience on live virtual hardware.

---

## 4. Benchmark Artifacts & Visualizations

Generated plots are stored in `results/graphs/` and can be inspected via the Streamlit dashboard or opened directly:
- `results/graphs/packet_loss_comparison.png`: Shows the reactive blackout spike vs flat proactive line.
- `results/graphs/rtt_comparison.png`: Demonstrates latency continuity through the reroute event.
- `results/tables/experiment_comparison.md`: Detailed tabular breakdown of all benchmark runs.
