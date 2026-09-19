# Technical Implementation Specification: AI-Driven Adaptive Self-Healing Network

This document provides complete technical specifications of the modules, classes, API contracts, algorithms, and mathematical formulations powering the self-healing network prototype.

---

## 1. Project Directory & Package Structure

```text
ai-adaptive-self-healing-network/
├── app.py                     # Streamlit NOC Dashboard (SIMULATION & CML modes)
├── demo.py                    # 8-Phase automated end-to-end self-healing demonstration
├── train.py                   # Machine learning data synthesis & model training script
├── START_PROJECT.bat          # Windows one-click automated bootstrap and launcher
├── config.yaml                # Primary network, ML, and QoS profile configurations
├── .env                       # CML controller credentials and device SSH passwords (git-ignored)
├── cml/                       # Cisco Modeling Labs assets
│   ├── topology.yaml          # 5-Node redundant Cisco topology definition for CML
│   ├── README_CML_SETUP.md    # Complete CML installation & configuration guide
│   └── configs/               # Cisco IOS startup configuration files
│       ├── R1.cfg, SW1.cfg, SW2.cfg, SW3.cfg, R2.cfg
├── src/
│   ├── cml/                   # CML 2.x REST API Client package
│   │   ├── __init__.py
│   │   └── cml_client.py      # REST token auth, lab lifecycle queries, diagnostics
│   ├── telemetry/             # Telemetry collection, parsing, and simulation
│   │   ├── collector.py       # Normalized telemetry collector (CML + Simulation)
│   │   ├── parser.py          # Cisco IOS CLI regex output parsing
│   │   └── simulator.py       # Deterministic 8-scenario network state engine
│   ├── features/              # Time-series trend analytics & slope extraction
│   │   └── feature_engine.py  # Rolling OLS linear slopes and instability score
│   ├── prediction/            # Machine learning failure & TTF prediction
│   │   ├── failure_predictor.py # DecisionTreeClassifier with explainability indicators
│   │   └── ttf_predictor.py   # Physical trajectory extrapolation & regression
│   ├── decision/              # Confidence gating and policy enforcement
│   │   └── decision_engine.py # Decision arbiter with dry-run safety interception
│   ├── routing/               # Cisco network automation and QoS path evaluation
│   │   ├── path_evaluator.py  # MCDA multi-criteria QoS penalty scoring
│   │   └── cisco_controller.py# CiscoController (Netmiko + CMLClient + Simulated)
│   ├── feedback/              # Closed-loop evaluation & anti-flapping hysteresis
│   │   └── feedback_engine.py # Confusion matrix classification & stability timer
│   ├── experiments/           # Empirical benchmark evaluation
│   │   ├── reactive_experiment.py # OSPF dead-timer convergence benchmark
│   │   ├── proactive_experiment.py# AI proactive preemption benchmark
│   │   └── compare_experiments.py # Statistical comparison and report generation
│   └── utils/                 # Logging and configuration utilities
│       ├── config_loader.py
│       └── logger.py
└── tests/                     # Unit and integration test suites
    ├── test_cml_integration.py     # CML REST, parser, dry-run, normalization tests
    ├── test_scenario_simulation.py # Step progression and scenario switching tests
    ├── test_cisco_controller.py    # CiscoController CLI command tests
    ├── test_decision.py            # Decision engine and confidence gate tests
    ├── test_features.py            # Feature extraction and OLS slope tests
    ├── test_feedback.py            # Feedback engine and hysteresis timer tests
    ├── test_path_evaluator.py      # QoS path evaluation tests
    └── test_prediction.py          # Failure predictor and TTF model tests
```

---

## 2. Component Implementation Details

### 2.1 CML REST Client (`src/cml/cml_client.py`)
- **Class**: `CMLClient(config=None, host="", username="", password="", lab_id="", port=443, verify_ssl=False)`
- **Core Methods**:
  - `authenticate(timeout=4.0) -> bool`: Dispatches `POST /api/v0/authenticate` with username/password payload. Receives JWT bearer token used in subsequent requests.
  - `test_connectivity() -> Dict[str, Any]`: Performs diagnostic check, returning `STATUS_NOT_CONFIGURED`, `STATUS_CONNECTING`, `STATUS_CONNECTED`, or `STATUS_ERROR` with structured diagnostic payload.
  - `get_lab_details() -> Dict[str, Any]`: Queries `GET /api/v0/labs/{lab_id}` for state, title, and node count.
  - `get_nodes() -> List[Dict[str, Any]]`: Queries `GET /api/v0/labs/{lab_id}/nodes` to discover active devices.
  - `get_links() -> List[Dict[str, Any]]`: Queries `GET /api/v0/labs/{lab_id}/links`.

### 2.2 Cisco Output Parser (`src/telemetry/parser.py`)
- **Class**: `CiscoOutputParser`
- **Static Methods**:
  - `parse_interface_brief(output: str) -> Dict[str, Dict[str, Any]]`: Parses `show ip interface brief`, extracting IP address, administrative status, and line protocol state (`is_up`).
  - `parse_counters_errors(output: str) -> Dict[str, Dict[str, int]]`: Parses `show interfaces counters errors`, capturing `align_err`, `fcs_crc_err`, `xmit_err`, `rcv_err`, and `total_errors`.
  - `parse_interface_detail(output: str) -> Dict[str, Any]`: Parses `show interfaces <name>`, capturing CRC errors, input errors, output errors, collisions, and line utilization.
  - `parse_ospf_neighbors(output: str) -> List[Dict[str, Any]]`: Parses `show ip ospf neighbor`, identifying neighbor IDs, states (e.g. `FULL/BDR`), and interface bindings.
  - `parse_ospf_interface(output: str) -> Dict[str, Any]`: Parses `show ip ospf interface <name>`, extracting active OSPF cost and area ID.
  - `parse_ping_output(output: str) -> Dict[str, float]`: Parses Cisco ping output, returning `rtt` (average ms), `jitter` (max - min ms), and `packet_loss` (percentage).
  - `parse_ip_route_ospf(output: str) -> List[Dict[str, Any]]`: Parses `show ip route ospf`, extracting destination prefixes, metrics, and egress interfaces.

### 2.3 Cisco Controller (`src/routing/cisco_controller.py`)
- **Class**: `CiscoController(config: Dict[str, Any])`
- **Core Operations**:
  - `connect() -> bool`: Initializes CML REST API connection and establishes Netmiko SSH sessions to Cisco switches.
  - `verify_cml_connection() -> Dict[str, Any]`: Comprehensive health check across both CML REST and switch SSH nodes.
  - `change_metric(device, interface, new_cost) -> bool`: Modifies OSPF interface cost. If `dry_run` is enabled, records command audit without modifying device.
  - `restore_metric(device, interface, original_cost=10) -> bool`: Resets baseline OSPF cost upon verified recovery.
  - `shutdown_interface(device, interface) -> bool`: Controlled failure injection executing `interface <name>` -> `shutdown`.
  - `enable_interface(device, interface) -> bool`: Restores interface via `no shutdown`.
  - `verify_routing(device) -> Dict[str, Any]`: Queries `show ip route ospf` to confirm traffic migration to the backup transit path via SW3.

### 2.4 Telemetry Collector (`src/telemetry/collector.py`)
- **Class**: `TelemetryCollector(config, cisco_controller=None)`
- **Normalizes Schema**:
  Guarantees both `NetworkSimulator` and live Cisco CML nodes produce identical schemas containing `timestamp`, `device`, `interface`, `path_id`, `rtt`, `jitter`, `packet_loss`, `crc_errors`, `input_errors`, `output_errors`, `utilization`, `link_status`, and `ospf_cost`.

---

## 3. Mathematical Formulations

### 3.1 Rate-of-Change Slopes (Ordinary Least Squares)
Given a metric series $Y = [y_0, y_1, \dots, y_{W-1}]$ across window $W$:
$$\bar{x} = \frac{W - 1}{2}, \quad \bar{y} = \frac{1}{W} \sum_{k=0}^{W-1} y_k$$
$$\text{Slope}_W(Y) = \frac{\sum_{k=0}^{W-1} (k - \bar{x})(y_k - \bar{y})}{\sum_{k=0}^{W-1} (k - \bar{x})^2}$$

### 3.2 Multidimensional Instability Index
Aggregates packet loss, jitter slope, CRC error rate, and interface flaps:
$$I_t = w_{loss} \cdot \tilde{L}_t + w_{jit} \cdot \tilde{S}_{jitter} + w_{crc} \cdot \tilde{G}_{crc} + w_{flap} \cdot \tilde{F}_t$$
Configured weights: $w_{loss} = 0.35, w_{jit} = 0.25, w_{crc} = 0.25, w_{flap} = 0.15$.

### 3.3 Dynamic Time-to-Failure (TTF) Extrapolation
$$\tau_{loss} = \frac{\max(0, L_{crit} - L_t)}{\max(\epsilon, \text{Slope}_W(L))} \times 1000 \text{ ms}$$
$$\widehat{\text{TTF}} = \tau_{loss} \times \max\left(0.6, 1.0 - \frac{I_t}{200}\right)$$
$$\text{Horizon Range} = [\max(100, \widehat{\text{TTF}} \times 0.85), \widehat{\text{TTF}} \times 1.15] \text{ ms}$$

### 3.4 QoS Path Penalty Scoring
For path $P$ with latency $L$, loss $P_L$, utilization $U$, risk $R$, and hop count $H$:
$$\text{Score}(P) = w_{lat} \frac{L}{150} + w_{loss} \frac{P_L}{20} + w_{util} \frac{U}{100} + w_{risk} R + w_{hop} \frac{H}{6} + \text{Penalty}_{QoS}$$
Where application profiles dynamically reweight priorities for **VOIP**, **VIDEO**, and **NORMAL_DATA**.
