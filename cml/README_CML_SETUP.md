# Cisco Modeling Labs (CML) Deployment & Configuration Guide

This guide details the complete procedure for deploying and running the **AI-Driven Adaptive Self-Healing Network** topology on Cisco Modeling Labs (CML-Personal / CML-Enterprise).

---

## 1. Hardware & Software Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Host OS** | Windows 11 64-bit | Windows 11 64-bit |
| **CPU** | 4 Cores (VT-x / AMD-V enabled) | 8 Cores (Intel i5-13420H or higher) |
| **Host RAM** | 16 GB Physical RAM | 16 GB - 32 GB RAM |
| **VM Hypervisor** | VMware Workstation Pro 17+ (Free for Personal Use) | VMware Workstation Pro 17+ |
| **CML Version** | CML 2.6 / 2.7 / 2.8 OVA | CML 2.7+ |
| **Reference Images** | IOSv (Router), IOSvL2 (Switch) | Refplat ISO bundled with CML |

---

## 2. Step-by-Step Installation Procedure

### Step 2.1: Install VMware Workstation Pro (Free)
1. Download **VMware Workstation Pro 17** from Broadcom's official portal (now free for personal desktop use).
2. Install with default virtualization enhancements.
3. In Windows BIOS/UEFI, verify **Intel Virtualization Technology (VT-x)** is enabled.

### Step 2.2: Deploy CML Virtual Machine
1. Open VMware Workstation Pro -> `File` -> `Open...` -> select `cml2_p_controller-*.ova`.
2. Name the VM: `CML-Controller`.
3. Allocate VM Resources:
   - **vCPUs**: 4 or 6 vCPUs (Enable *Virtualize Intel VT-x/EPT* in VM Processor settings).
   - **RAM**: 6 GB to 8 GB RAM (Leaving 8 GB for Windows and Python ML processing).
   - **Network Adapter 1**: Bridged (or NAT with Port Forwarding for 443 and SSH).
4. Power On VM and complete the initial Linux console setup (`sysadmin` account and IP assignment, e.g., `192.168.1.100`).

### Step 2.3: Access the CML Web Interface
1. Open a browser on Windows and navigate to `https://192.168.1.100` (accept self-signed TLS cert).
2. Log in using your configured CML admin credentials.

---

## 3. Importing the Lab Topology

1. In the CML Dashboard, click **Import**.
2. Select the file: `cml/topology.yaml` from this project repository.
3. The 5-node redundant topology will load:
   - `R1`: Source Gateway (IOSv)
   - `SW1`: Core Distribution Ingress (IOSvL2)
   - `SW2`: Core Distribution Egress (IOSvL2)
   - `SW3`: Redundant Transit Path (IOSvL2)
   - `R2`: Destination Gateway (IOSv)
4. Click **Start Lab** (Green play icon). All 5 nodes will boot in ~2 minutes.

---

## 4. Applying Cisco Node Configurations

Copy and paste the configuration files from `cml/configs/` into each node's console via CML Web Console or SSH:

- `cml/configs/R1.cfg` -> Apply to Node **R1**
- `cml/configs/SW1.cfg` -> Apply to Node **SW1**
- `cml/configs/SW2.cfg` -> Apply to Node **SW2**
- `cml/configs/SW3.cfg` -> Apply to Node **SW3**
- `cml/configs/R2.cfg` -> Apply to Node **R2**

---

## 5. Network Addressing & OSPF Architecture Table

| Device | Interface | IP Address / Mask | Subnet Description | Default OSPF Cost |
| :--- | :--- | :--- | :--- | :--- |
| **R1** | Loopback0 | `192.168.1.1/24` | Source Subnet (Simulated Host: `192.168.1.10`) | 1 |
| **R1** | Gi0/0 | `10.0.12.1/30` | R1 <-> SW1 Transit | 10 |
| **SW1**| Gi0/0 | `10.0.12.2/30` | SW1 <-> R1 Transit | 10 |
| **SW1**| Gi0/1 | `10.0.23.1/30` | **Primary Link** (SW1 <-> SW2) | **10** |
| **SW1**| Gi0/2 | `10.0.13.1/30` | **Backup Link** (SW1 <-> SW3) | **10** |
| **SW2**| Gi0/1 | `10.0.23.2/30` | **Primary Link** (SW2 <-> SW1) | **10** |
| **SW2**| Gi0/2 | `10.0.32.2/30` | **Backup Link** (SW2 <-> SW3) | **10** |
| **SW2**| Gi0/0 | `10.0.24.1/30` | SW2 <-> R2 Transit | 10 |
| **SW3**| Gi0/2 | `10.0.13.2/30` | SW3 <-> SW1 Transit | 10 |
| **SW3**| Gi0/1 | `10.0.32.1/30` | SW3 <-> SW2 Transit | 10 |
| **R2** | Gi0/0 | `10.0.24.2/30` | R2 <-> SW2 Transit | 10 |
| **R2** | Loopback0 | `192.168.2.1/24` | Destination Subnet (Simulated Host: `192.168.2.10`)| 1 |

### Routing Metrics Summary
- **Primary Path** (`R1 -> SW1 -> SW2 -> R2`): Total OSPF Cost = $10 + 10 + 10 = \mathbf{30}$ (Preferred)
- **Backup Path** (`R1 -> SW1 -> SW3 -> SW2 -> R2`): Total OSPF Cost = $10 + 10 + 10 + 10 = \mathbf{40}$
- **AI Preemptive Reroute Action**: AI triggers `ip ospf cost 100` on `SW1 Gi0/1`.
  - New Primary Cost = $10 + 100 + 10 = \mathbf{120}$.
  - Backup Path ($40$) immediately becomes the Active OSPF Shortest Path before link failure!

---

## 6. Verifying Connectivity from Windows Host

1. Configure `.env` in the project root:
   ```bash
   ENV_MODE=CML
   CML_HOST=192.168.1.100
   CML_USER=admin
   CML_PASS=cml_password
   CISCO_USERNAME=admin
   CISCO_PASSWORD=cisco123!
   ```
2. Verify Python-to-CML connectivity:
   ```bash
   python main.py --mode cml --verify-connectivity
   ```
3. If CML is not installed or offline, run the prototype in full simulation mode:
   ```bash
   python main.py --mode simulation
   ```
