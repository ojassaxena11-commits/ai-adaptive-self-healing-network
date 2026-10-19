# AI-Driven Adaptive Self-Healing Network

> **A Complete AI-Powered Network Self-Healing System for Early Failure Prediction, Route Comparison, and Safe Automated Recovery across GNS3 and High-Fidelity Simulation.**

---

## 1. Project Overview & Problem Statement

Standard computer networks rely on routing protocols like **OSPF** to direct traffic along the shortest path. However, traditional routing protocols are purely **reactive**: they only notice that a link is broken after it completely fails or keepalive timers expire (typically 4–40 seconds). During that outage window, data packets are lost, causing dropped calls on Voice over IP (VoIP), broken video streams, and transaction failures.

This project solves that problem with an **Adaptive Risk-Aware AI-Based Self-Healing Network**.
Instead of waiting for links to crash, the system:
1. **Collects network data** continuously (latency, jitter, packet loss, hardware errors, and traffic load).
2. **Predicts network problems early** before total collapse using explainable machine learning and estimates the time before failure.
3. **Compares available network routes** using traffic quality (QoS) priorities.
4. **Changes the network route safely** (updating OSPF route cost from 10 to 100) to steer traffic to a healthy backup route with **zero downtime and zero packet loss**.
5. **Checks whether the fix worked** by verifying routing state and link stability.

---

## 2. Key Features

- **Integrated GNS3 Network Controller**:
  - Connects directly to the official **GNS3 Controller API** at `http://localhost:3080`.
  - Works with free built-in GNS3 switch templates (no proprietary Cisco IOS images required).
  - Configurable server address, port, and authentication credentials.
  - Automatically lists available projects and builds the self-healing network topology with one click.
- **High-Fidelity Simulation Mode**:
  - Seamless offline mode that lets you test and demonstrate all 8 scenarios even when GNS3 is not running.
- **Predict Network Problems with AI**:
  - Decision Tree classifier that detects subtle patterns of degradation (like rising jitter slope and CRC error growth).
  - Estimates the time before link failure so action is taken early.
- **Smart Safety Gates**:
  - Rejects uncertain predictions (confidence threshold >= 80%) to avoid false alarms.
  - Safe Test Mode (Dry Run) to inspect proposed routing changes before applying them.
  - Operator confirmation toggles before applying live changes.
  - Anti-flapping stability timer to prevent rapid route oscillation.
- **Interactive NOC Dark Dashboard**:
  - Built with Streamlit in `app.py`.
  - Live interactive SVG network map with directional traffic flow, link status badges, and route highlighting.
  - Beginner-friendly English labels for buttons, status indicators, and tooltips.
  - 7-Phase interactive guided demo stepper.
  - Telemetry trend charts and benchmark comparisons.

---

## 3. How the System Works (Architecture)

```text
              [ Live GNS3 Network ]  OR  [ High-Fidelity Simulator ]
                                       ↓
                             Collect Network Data
                                       ↓
                           Derive Trend Features
                                       ↓
                         Predict Network Problems
                                       ↓
                       Estimated Time Before Failure
                                       ↓
                       Check Whether Action Is Needed
                                       ↓
                           Compare Network Routes
                                       ↓
                            Check Recovery Safety
                                       ↓
                            Change Network Route
                                       ↓
                       Check Whether the Fix Worked
                                       ↓
                         Update Streamlit Dashboard
```

---

## 4. Network Topology

The project models a redundant enterprise network topology:

```text
                 [ R1: Source Gateway Router ]
                               |
                               v
               +-------------------------------+
               | SW1: Ingress Switch (AI Target)|
               +-------------------------------+
                      /                 \
     (Primary Route: Cost 10)     (Backup Route: Cost 10)
                    /                     \
                   v                       v
   +-------------------------------+     +-------------------------------+
   | SW2: Egress Switch            | <---| SW3: Backup Transit Switch    |
   +-------------------------------+     +-------------------------------+
                   |
                   v
              [ R2: Destination Gateway Router ]
```

- **Primary Route** (`R1 → SW1 → SW2 → R2`): Total baseline OSPF cost = **30** (Active by default).
- **Backup Route** (`R1 → SW1 → SW3 → SW2 → R2`): Total baseline OSPF cost = **40** (Standby).
- **Self-Healing Action**: When degradation is detected on `SW1-Gi0/1`, the controller changes its cost to **100**. The primary path cost becomes $120$, causing traffic to naturally diverge to the backup route ($40$) **before the physical link fails**.

---

## 5. Beginner-Friendly Windows Setup Guide

### Step 1: Open GNS3
1. Launch **GNS3** on your Windows PC.
2. GNS3 will automatically start its local controller at `http://localhost:3080`.
3. If GNS3 has authentication enabled (default username `admin`), the dashboard auto-detects it from your local configuration or reads `GNS3_USER` and `GNS3_PASS` from `.env`.

### Step 2: Install & Run the Project

#### Easy One-Click Method:
Double-click **`START_PROJECT.bat`** in the project folder.

#### Or Manual PowerShell Method:
```powershell
# Navigate to the project directory
cd "C:\Users\ojass\OneDrive\Desktop\computer networks project"

# Run the Streamlit web dashboard
.venv\Scripts\python -m streamlit run app.py
```

### Step 3: Connect the Dashboard to GNS3
1. Open the dashboard in your browser (usually `http://localhost:8501`).
2. In the left sidebar under **Select Environment**, choose **`GNS3`**.
3. Click the button: **`🔌 Check Connection to GNS3`**.
4. You will see a green badge: **`GNS3 CONNECTED ✓`**.
5. If you do not have a project yet, click **`🔨 Build Topology in GNS3`**. The dashboard will automatically create `AI-Self-Healing-Network` with nodes `R1`, `SW1`, `SW2`, `SW3`, `R2` and all required connections!

### Step 4: Run the Demonstration
1. Click **`📡 Collect Network Data`** to sample the network state.
2. Click **`🧠 Predict Network Problems`** to evaluate link health with AI.
3. Click **`🎯 Compare Network Routes`** to verify the backup candidate path.
4. Click **`⚡ Change Network Route`** to test safe proactive rerouting.
5. Click **`🔍 Check Whether the Fix Worked`** to verify that traffic migrated successfully.
6. You can also test offline simulation anytime by toggling back to **`SIMULATION`** mode.

---

## 6. Device Templates & Images in GNS3

- **Built-in Ethernet Switch (Default & Free)**:
  - 100% free and included inside GNS3.
  - Requires no license or proprietary image download.
  - Supports live link creation, topology inspection, and link suspension (fault injection).
- **Optional Cisco IOS Images (For Real CLI Automation)**:
  - If you have an authorized Cisco Dynamips image (such as `c7200-adventerprisek9-mz.152-4.M11.image`) or Cisco IOU/IOSv, you can add it in GNS3 under **Edit → Preferences → Dynamips → IOS routers**.
  - When Cisco IOS routers are used, the system can connect via Telnet/SSH console to execute live `ip ospf cost` and `show ip route ospf` commands.

---

## 7. Troubleshooting Common Connection Issues

| Issue / Error Message | Cause | Solution |
| :--- | :--- | :--- |
| **Cannot Connect to GNS3: Server is offline** | GNS3 is not opened or the local server is stopped. | Start GNS3 on your PC and wait for the local server to say *started* on port 3080. |
| **Cannot Connect to GNS3: Incorrect username or password (HTTP 401)** | GNS3 server has authentication enabled. | In the sidebar under **GNS3 Server Settings**, enter the correct username and password, then click *Save & Reconnect*. |
| **No GNS3 project is currently selected** | GNS3 has no open project. | Click **🔨 Build Topology in GNS3** in the sidebar to auto-create the project. |
| **Missing nodes or paths** | Selected project does not have the required 5 devices. | Click **🔨 Build Topology in GNS3** or select the `AI-Self-Healing-Network` project. |

---

## 8. Running the Automated Test Suite

To run all 62 unit and integration tests across the project:

```powershell
.venv\Scripts\python -m unittest discover tests -v
```

Expected output:
```text
Ran 62 tests in 5.3s
OK
```

---

## 9. Configuration Files

- **`config/config.yaml`**: Main configuration for topology, GNS3 settings, telemetry parameters, decision thresholds, and QoS weights.
- **`.env.example`**: Example environment variables for GNS3 host, port, username, and password.
- **`app.py`**: Main Streamlit web application.
- **`src/gns3/gns3_client.py`**: Official GNS3 Controller REST API v2 integration module.
- **`src/routing/cisco_controller.py`**: Routing automation and safety verification controller.
- **`src/visualization/topology_visualizer.py`**: NOC dark-navy interactive SVG network topology renderer.
