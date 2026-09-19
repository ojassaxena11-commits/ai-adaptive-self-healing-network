# Cisco Modeling Labs (CML) Deployment & Configuration Guide

This guide details the complete procedure for deploying, configuring, and operating the **AI-Driven Adaptive Self-Healing Network** on Cisco Modeling Labs (CML-Personal / CML-Enterprise) or running seamlessly in high-fidelity SIMULATION mode.

---

## 1. Operating Modes Overview

The system features **ONE unified Streamlit GUI** with two selectable operational environments:

1. **SIMULATION MODE**:
   - Runs on a high-fidelity, deterministic mathematical state engine (`NetworkSimulator`).
   - Requires **no external hardware, VMs, or CML license**.
   - Supports 8 distinct real-world failure scenarios, interactive progression via `▶ Step Once`, automated live demonstration, ML retraining, and reactive vs proactive comparative benchmarking.
   - Ideal for quick demonstrations, oral presentations, grading, and automated unit testing.

2. **CML MODE**:
   - Connects to a live Cisco Modeling Labs 2.x instance running actual Cisco IOSv router and Cisco IOSvL2 switch images.
   - Queries telemetry across two operational planes:
     - **CML REST API** (Port 443): Authenticates via JWT, monitors lab status, node lifecycle states, and link connectivity.
     - **Cisco Switch SSH / Netmiko** (Port 22): Gathers hardware interface error counters (`show interfaces counters errors`), link state (`show ip interface brief`), OSPF neighbors (`show ip ospf neighbor`), OSPF cost (`show ip ospf interface`), and ping probes.
   - Normalizes live Cisco telemetry into the identical schema used by the AI pipeline.
   - Preemptively updates OSPF interface metrics (`ip ospf cost 10 -> 100`) via automated Cisco CLI configuration sessions.
   - Verifies OSPF routing table convergence (`show ip route ospf`) to guarantee traffic has migrated to the backup path.
   - Includes safe **DRY_RUN mode** (auditing commands without device mutation) and **Controlled Failure Injection** with safety confirmation toggles.

---

## 2. Hardware & Virtualization Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Host OS** | Windows 10/11 (64-bit), Linux (Ubuntu 22.04+), or macOS | Windows 11 (64-bit) |
| **CPU** | 4 Cores (Intel VT-x / AMD-V virtualization enabled in BIOS) | 8 Cores (Intel Core i5/i7/i9 or AMD Ryzen 7/9) |
| **Host RAM** | 16 GB Physical RAM | 16 GB - 32 GB Physical RAM |
| **VM Hypervisor** | VMware Workstation Pro 17+ (Free for Personal Use) | VMware Workstation Pro 17+ |
| **CML Version** | CML-Personal 2.6 / 2.7 / 2.8 OVA | CML 2.7+ |
| **Cisco Reference Images** | IOSv (Router), IOSvL2 (Switch) | Bundled with CML Refplat ISO |

---

## 3. Step-by-Step CML Deployment Procedure

### Step 3.1: Hypervisor & Virtualization Setup
1. Download and install **VMware Workstation Pro 17** (free for personal desktop use from Broadcom).
2. Ensure hardware virtualization is enabled in your system BIOS/UEFI (**Intel VT-x** or **AMD-V**).
3. In Windows, verify that Windows Hypervisor Platform / WSL2 does not conflict with VMware VT-x nested virtualization.

### Step 3.2: Deploy CML Virtual Machine
1. In VMware Workstation Pro, click `File` -> `Open...` -> select `cml2_p_controller-*.ova`.
2. Name the virtual machine: `CML-Controller`.
3. Configure VM resource allocations:
   - **vCPUs**: Allocate 4 or 6 vCPUs.
   - **Virtualization Engine**: Check **"Virtualize Intel VT-x/EPT or AMD-V/RVI"**.
   - **RAM**: Allocate 6 GB to 8 GB RAM (leaving at least 8 GB for your host OS, Streamlit, and Python ML).
   - **Network Adapter 1**: Set to **Bridged** (recommended to obtain an IP on your local subnet) or **NAT** with port forwarding.
4. Power on the VM and follow the terminal console wizard to configure the `sysadmin` account and system IP (e.g., `192.168.1.100` or DHCP).

### Step 3.3: Web Portal Access & Licensing
1. Open a browser on your host machine and navigate to:
   ```text
   https://<CML_HOST_IP>   (e.g., https://192.168.1.100)
   ```
2. Accept the self-signed TLS certificate warning.
3. Log in with your CML administrative credentials.
4. Register your CML license token in `Tools` -> `Licensing` if required.

---

## 4. Importing the Self-Healing Topology

1. From the CML Web Dashboard, click **Import**.
2. Browse and select the file: `cml/topology.yaml` from this repository.
3. The 5-node redundant network will be rendered:
   - `R1`: Source Gateway (Cisco IOSv)
   - `SW1`: Core Ingress Distribution Switch (Cisco IOSvL2) — Primary AI automation target
   - `SW2`: Core Egress Distribution Switch (Cisco IOSvL2)
   - `SW3`: Redundant Transit Switch (Cisco IOSvL2) — Standby backup path
   - `R2`: Destination Gateway (Cisco IOSv)
4. Click **Start Lab** (the green play button). Allow 2–3 minutes for all nodes to reach `STARTED` state.

---

## 5. Applying Node Configurations

You can apply configurations using the CML Console or SSH into each node directly.
Copy and paste the configurations located in `cml/configs/`:

| Node Name | Configuration File | Management IP | Primary Role |
| :--- | :--- | :--- | :--- |
| **R1** | `cml/configs/R1.cfg` | `10.0.12.1` | Source Gateway generating test packet streams |
| **SW1**| `cml/configs/SW1.cfg`| `10.0.12.2` | Core Ingress Switch (OSPF metric manipulated here) |
| **SW2**| `cml/configs/SW2.cfg`| `10.0.24.1` | Core Egress Switch connecting to R2 |
| **SW3**| `cml/configs/SW3.cfg`| `10.0.13.2` | Redundant Standby Transit Switch |
| **R2** | `cml/configs/R2.cfg` | `10.0.24.2` | Destination Gateway receiving traffic |

### Network Addressing & OSPF Metric Architecture
- **Primary Path** (`R1 -> SW1 -> SW2 -> R2`):
  - Interface: `SW1:Gi0/1 ↔ SW2:Gi0/1`
  - Baseline OSPF Cost: $10 + 10 + 10 = \mathbf{30}$ (**ACTIVE / Preferred**)
- **Backup Path** (`R1 -> SW1 -> SW3 -> SW2 -> R2`):
  - Interfaces: `SW1:Gi0/2 ↔ SW3:Gi0/2`, `SW3:Gi0/1 ↔ SW2:Gi0/2`
  - Baseline OSPF Cost: $10 + 10 + 10 + 10 = \mathbf{40}$ (**STANDBY**)
- **Proactive Reroute Action**:
  - AI executes: `interface GigabitEthernet0/1` -> `ip ospf cost 100` -> `end`
  - New Primary Cost: $10 + 100 + 10 = \mathbf{120}$
  - Backup Path (Cost $40$) immediately becomes the lowest-cost path in OSPF Area 0!
  - SPF recalculation diverts traffic to SW3 **with zero packet loss and zero downtime**.

---

## 6. Environment Configuration (`.env`)

Create or update the `.env` file in the project root. **Never commit real credentials to version control.** `.env` is included in `.gitignore`.

```ini
# Operational Environment: SIMULATION or CML
MODE=SIMULATION

# Cisco Modeling Labs (CML) Controller REST API Configuration
CML_HOST=192.168.1.100
CML_PORT=443
CML_USER=admin
CML_PASS=YourCmlPasswordHere
CML_LAB_ID=lab-adaptive-mesh
CML_VERIFY_SSL=false

# Cisco Device SSH Credentials (for IOSv / IOSvL2 nodes)
CISCO_USERNAME=cisco
CISCO_PASSWORD=cisco
CISCO_ENABLE_SECRET=cisco

# Controller Dry Run Safety Mode (true = audit commands only; false = execute live)
DRY_RUN=false
```

---

## 7. Connecting & Running the GUI

### Option 1: Double-Click Launcher (Windows)
Double-click `START_PROJECT.bat` in the project root. This launcher automatically:
- Checks Python installation
- Validates or creates virtual environment
- Installs required packages
- Launches Streamlit at `http://localhost:8501`

### Option 2: Command Line
```powershell
# Activate your virtual environment if applicable
# .venv\Scripts\activate

# Launch Streamlit dashboard
streamlit run app.py
```

---

## 8. Live Demonstration Guide for Teachers & Evaluators

### Demonstration A: SIMULATION Mode (Instant & Deterministic)
1. In the sidebar, select **Environment: `[ SIMULATION ]`**.
2. Set **Traffic Class** to `VOIP` (high sensitivity to latency and packet loss).
3. Select **Scenario: `Scenario 4: Failure with Backup Preemption`**.
4. Click **▶ Step Once** consecutively:
   - **Step 1–2**: Network is healthy (RTT ~11ms, Jitter ~1.5ms, Loss 0.0%). AI shows `HEALTHY` (Risk < 10%).
   - **Step 3–4**: Jitter and CRC errors accelerate. AI transitions to `WARNING` -> `HIGH_RISK` ($P \ge 75\%$, Confidence $\ge 80\%$, TTF ~4.2s).
   - **Decision Engine triggers `PREEMPTIVE_REROUTE`**.
   - OSPF cost on `SW1:Gi0/1` updates from 10 to 100. Active path changes to `R1 → SW1 → SW3 → SW2 → R2`.
   - **Step 5**: Primary link physically collapses (`DOWN`). Notice that active traffic is already on the backup path with **0.0% packet loss**!
5. Run the **Full Self-Healing Demo**:
   - Click **`▶ RUN FULL SELF-HEALING DEMO`** on the main page.
   - Watch the 8-phase automated cycle finish with an achieved lead time of over **1,200 ms** before failure and **0% loss**.
6. Run the **Benchmark Comparison**:
   - Click **`📊 RUN REACTIVE VS PROACTIVE BENCHMARK`**.
   - Review comparative metrics: **96% packet loss reduction** and **100% convergence downtime elimination**.

### Demonstration B: CML Live Mode (Physical Virtualization)
1. Ensure your CML VM is powered on with `cml/topology.yaml` started.
2. In the sidebar, select **Environment: `[ CML ]`**.
3. Click **`🔌 Verify CML Connection`**:
   - The status badge changes to **`CML CONNECTED ✓`**.
   - Diagnostics display CML REST reachability and node status.
4. Click **`📡 Collect Telemetry`**:
   - Real interface error counters and ping latencies are polled from SW1 and normalized.
5. Click **`🧠 Run AI Prediction`**:
   - Machine learning extracts rolling trend slopes and computes failure probability and TTF.
6. Click **`🎯 Evaluate Backup`**:
   - Candidate paths are ranked using the MCDA QoS penalty score.
7. Click **`⚡ Execute Reroute`**:
   - Modifies OSPF metric (`ip ospf cost 100`).
   - If `DRY_RUN` is ON: Displays the exact Cisco IOS commands that would be sent.
   - If `DRY_RUN` is OFF: Sends configuration to Cisco switch via Netmiko.
8. Click **`🔍 Verify Routing`**:
   - Inspects Cisco routing table (`show ip route ospf`).
   - Displays **`Traffic Migration: SUCCESS ✓`**.
9. Test **Controlled Failure Injection**:
   - Open the **💥 Controlled Failure Injection** expander in the sidebar.
   - Select **Interface failure (shutdown Gi0/1)**.
   - Check the **⚠️ Confirm Failure Injection** safety box.
   - Click **Inject Fault** to observe system response.
   - Click **Restore Link** to safely re-enable the port and restore baseline metric.
