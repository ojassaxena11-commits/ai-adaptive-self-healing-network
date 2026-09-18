# System Limitations & Engineering Constraints

In accordance with strict academic research integrity, this document details the engineering limitations, operational boundaries, and deployment considerations of the **Adaptive Risk-Aware AI-Based Self-Healing Network**.

---

## 1. Physical vs. Virtual Network Constraints

### 1.1 Control-Plane Automation via CLI vs. Model-Driven Telemetry
- **Current Prototype**: The Cisco controller interacts with devices using Netmiko/SSH CLI parsing (`show ip interface brief`, `show interfaces counters errors`, `show ip ospf neighbor`) and Cisco configuration commands (`ip ospf cost 100`).
- **Production Limitation**: While SSH is universally supported across legacy and modern Cisco gear, polling CLI counters over SSH introduces $\approx 200 - 500 \text{ ms}$ processing overhead per polling cycle.
- **Production Recommendation**: High-scale enterprise networks should transition from SSH polling to **Model-Driven Telemetry (MDT)** via **gRPC / gNMI** and push notifications (YANG models `Cisco-IOS-XE-interfaces-oper`), which stream interface state changes sub-millisecond without CPU interrupt penalties.

### 1.2 Virtualized Forwarding Planes (CML IOSv / IOSvL2)
- Cisco Modeling Labs utilizes **IOSv** (software-emulated router) and **IOSvL2** (software-emulated switch) images.
- These virtual appliances run the Cisco IOS control plane inside QEMU/KVM virtual machines. Packet forwarding is performed in software by the virtual CPU rather than dedicated Application-Specific Integrated Circuits (ASICs) or Ternary Content-Addressable Memory (TCAM).
- Consequently, line-rate hardware micro-bursts and hardware buffer queue drops are abstracted in CML.

---

## 2. Machine Learning Boundaries & Tradeoffs

### 2.1 False Positive vs. False Negative Tradeoff
- **False Positive (Type I Error)**: The model predicts link failure when the link is merely experiencing temporary congestion or bursty traffic.
  - *Risk*: Causes unnecessary route diversion, slightly increasing hop count and path latency.
  - *Mitigation*: The **Confidence Gate** ($C \ge 0.80$) and minimum multi-sample trend confirmation prevent premature diversion on transient spikes.
- **False Negative (Type II Error)**: A catastrophic physical failure occurs abruptly (e.g., fiber cable backhoe cut) without preceding gradual degradation.
  - *Behavior*: If no degradation signature precedes the outage, the AI cannot anticipate the failure. In this event, the network seamlessly falls back to standard reactive OSPF dead-timer convergence.
  - *Conclusion*: The AI system strictly augments OSPF; it never degrades standard protocol baseline reliability.

### 2.2 Time-to-Failure (TTF) Estimation Uncertainty
- Physical link degradation velocities fluctuate based on environmental interference (e.g., optical attenuation, electromagnetic noise, copper bend radius stress).
- TTF estimates are mathematically modeled as trajectory extrapolations with an uncertainty window of $\pm 15\%$. They provide an operational early-warning horizon rather than an absolute deterministic countdown.

---

## 3. Scope of Current Environment Deployment

| Capability | Current Windows Machine Status | Dual-Mode Resolution |
| :--- | :--- | :--- |
| **Python ML Engine** | Fully operational (Python 3.13, Scikit-learn, Pandas, Streamlit) | Runs natively on host |
| **Telemetry Simulator** | Fully operational (8 realistic continuous time-series degradation scenarios) | Primary development & demo engine |
| **Cisco Modeling Labs** | Not installed on host machine (VMware Workstation Pro & CML OVA required) | Ready-to-import `topology.yaml` & `configs/` supplied |
| **Labeling Transparency** | Strict source attribution (`REAL_CML` vs `SIMULATION`) | Prevents misleading viva claims |
