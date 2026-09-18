# Comprehensive Viva Voce Defense Guide: AI-Driven Adaptive Self-Healing Network

This document prepares project team members for examination questions across computer networking, machine learning, software automation, and research methodology.

---

### Q1: What is a Self-Healing Network?
**Answer:** A self-healing network is an autonomous architecture capable of detecting anomalous operating conditions, diagnosing faults or degradation trends, and executing corrective routing interventions automatically without requiring human operator intervention.

### Q2: Why was OSPF chosen over RIP or BGP?
**Answer:** 
- **RIP** is a distance-vector protocol with a slow hop-count metric, maximum 15 hops, and convergence times exceeding 30–60 seconds, making it unsuitable for real-time applications.
- **BGP** is an exterior gateway protocol optimized for inter-autonomous system policy routing rather than high-speed interior traffic steering.
- **OSPF** is a link-state interior gateway protocol utilizing Dijkstra's Shortest Path First (SPF) algorithm. It builds a complete topology database (LSDB), supports arbitrary link costs, and converges quickly. Crucially, OSPF path selection can be dynamically controlled by manipulating interface link metrics (`ip ospf cost`).

### Q3: What is Network Convergence, and why is Reactive Convergence Insufficient?
**Answer:** Convergence is the state where all network routers have updated their routing information bases (RIB/FIB) to agree on consistent, loop-free paths following a topology change. 
In standard OSPF, convergence is purely **reactive**: the protocol must wait for the physical carrier drop or the expiration of the Hello/Dead timer (typically 40 seconds by default, or 4–5 seconds in aggressive tuning) before recalculating routes. During this blackout window, incoming packets are sent into a black hole, resulting in massive packet loss, broken TCP connections, and dropped VoIP calls.

### Q4: Why introduce Machine Learning instead of static threshold rules?
**Answer:** Static threshold rules (e.g., "if loss > 5%, reroute") suffer from severe false positives caused by transient traffic bursts and cannot anticipate failure before it happens. Machine learning analyzes **multi-dimensional time-series dynamics** (joint correlation of jitter acceleration, CRC error velocity, and RTT drift) to detect subtle hardware degradation patterns *before* catastrophic threshold crossings occur.

### Q5: Why choose a Decision Tree over a Deep Neural Network?
**Answer:** 
1. **Explainability**: In enterprise networking and academic defense, black-box predictions are unacceptable. A Decision Tree provides transparent, auditable decision paths (e.g., "Jitter slope > 2.4 ms/sample AND CRC growth > 5").
2. **Computational Overhead**: Network controllers must evaluate telemetry in milliseconds. Decision trees have $O(\text{depth})$ inference complexity with near-zero CPU and memory footprint, allowing deployment on edge devices.
3. **No Overfitting on Low-Data Baselines**: Unlike deep networks that require millions of parameters, lightweight decision trees generalize well on structured tabular telemetry.

### Q6: What is Feature Engineering and why are trends (slopes) vital?
**Answer:** Feature engineering transforms raw instantaneous sensor readings into mathematically descriptive features. Instantaneous values (e.g., RTT = 25 ms) are ambiguous—they could represent normal latency or an impending crash. Linear regression slopes ($m = \frac{dy}{dt}$) across sliding windows (5, 10, 20 samples) capture the **velocity of degradation**. A positive jitter slope indicating acceleration is far more predictive of physical cable breakdown than raw jitter magnitude.

### Q7: What is the difference between Failure Probability, Confidence, and Time-to-Failure?
**Answer:**
- **Failure Probability ($P$)**: The model's estimated likelihood that the link belongs to an impaired or failing state ($[0.0, 1.0]$).
- **Confidence ($C$)**: The certainty margin of the classifier across class probability distributions ($\max_k P(y=k)$).
- **Time-to-Failure (TTF)**: A physical trajectory projection estimating remaining operational milliseconds before metrics cross critical breakdown thresholds ($[T_{min}, T_{max}] \text{ ms}$).

### Q8: Why does the system NOT reroute on every failure prediction?
**Answer:** To prevent **route flapping** and **congestive collapse**. Preemptive diversion is gated by:
1. **Confidence Gate**: Confidence must be $\ge 80\%$.
2. **Backup Health Check**: The candidate backup path must not be congested or degraded.
3. **QoS Alignment**: The backup must satisfy the application's latency/bandwidth constraints.

### Q9: How is the optimal candidate backup path selected?
**Answer:** Using a Multi-Criteria Decision Analysis (MCDA) heuristic formula:
$$\text{Score}(P) = w_{lat} \frac{\text{RTT}}{150} + w_{loss} \frac{\text{Loss}}{20} + w_{util} \frac{\text{Util}}{100} + w_{risk} \text{Risk} + w_{hop} \frac{\text{Hops}}{6} + \text{QoS Penalty}$$
The path with the lowest objective penalty score is selected.

### Q10: How does QoS awareness change path ranking?
**Answer:**
- For **VOIP**: Weights for packet loss (0.35) and latency (0.30) dominate.
- For **VIDEO**: Bandwidth utilization (0.35) and loss (0.25) dominate.
- For **NORMAL_DATA**: Hop count (0.25) and utilization (0.20) dominate.
A path with lower latency but 5% packet loss will be chosen for normal data but rejected for VoIP.

### Q11: How does Python communicate with Cisco hardware?
**Answer:** 
- **Simulation Mode**: Uses an in-memory high-fidelity state engine replicating Cisco IOS commands and OSPF cost calculations.
- **CML / Real Mode**: Connects via `netmiko` (SSHv2) or the CML REST API (`/api/v0/labs/...`), executing privileged Cisco CLI commands (`ip ospf cost 100`) and parsing standard command outputs (`show ip ospf neighbor`, `show interfaces counters errors`).

### Q12: What happens if the AI predicts a False Positive?
**Answer:** A False Positive means the AI predicted failure on a link that remained healthy. If confidence was high, traffic diverted to the backup path. The network continues operating normally because the backup is healthy, with only a minor sub-millisecond latency difference (via SW3). The feedback engine detects that no failure occurred, records a `FALSE_POSITIVE` in `data/events.csv`, and adjusts performance statistics.

### Q13: What happens if the AI predicts a False Negative?
**Answer:** A False Negative occurs when an abrupt physical outage happens without preceding warning telemetry (e.g. physical cable cut). In this scenario, the AI had no trend signals to act on. The network immediately falls back to standard OSPF reactive dead-timer convergence. Thus, the AI system can only improve or match baseline OSPF; it never worsens it.

### Q14: How does the system prevent Route Flapping when the primary link recovers?
**Answer:** Using the **Anti-Flapping Route Restoration Hysteresis Engine**. When the primary link comes back UP, the system does NOT immediately switch back. It initiates a 15-second observation timer and requires a minimum of 10 consecutive samples where $P(\text{Failure}) < 0.15$. If the link flaps or emits CRC errors during this period, the timer resets and traffic remains safely on the backup.

### Q15: What is the achieved experimental lead time and packet loss reduction?
**Answer:**
- **Failure Lead Time**: The AI predicted the failure and rerouted traffic **4,500 ms** before physical link collapse.
- **Packet Loss**: Traditional reactive OSPF suffered **20.0% packet loss** (5,000 ms blackout window). The AI proactive system achieved **0.0% loss** during link cut and **0.8% total loss** overall (**96% loss reduction**).
- **Downtime**: Reduced from 5,000 ms to **0 ms**.

### Q16: What is implemented vs simulated in this project?
**Answer:** The Python ML pipeline (feature engineering, Decision Tree, TTF regression, confidence gating, QoS path scoring, hysteresis, Streamlit dashboard, and tests) is 100% fully implemented and functional. Network telemetry is driven by an in-memory high-fidelity simulator that models exact OSPF topologies and link degradation physics. Full Cisco Modeling Labs configuration scripts (`topology.yaml`, `R1.cfg`–`SW3.cfg`) and SSH integration drivers are provided for live CML deployment.

### Q17: Is this system patentable?
**Answer:** While aspects of predictive routing have prior art in academic literature and enterprise patents (e.g., Cisco proactive BFD, SD-WAN SLA steering), the novel integrated combination of **multi-dimensional physical degradation trend slopes, confidence-gated decision arbiter, dynamic traffic QoS re-weighting, and stability-damped OSPF metric mutation** presents valid research novelty suitable for conference publication and preliminary patent disclosure documentation (`docs/invention_notes.md`).
