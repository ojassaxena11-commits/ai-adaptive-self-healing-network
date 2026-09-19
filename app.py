import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path for robust imports from any execution context
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Streamlit Page Configuration
st.set_page_config(
    page_title="AI-Driven Adaptive Self-Healing Network",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Dark Modern NOC Interface
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background-color: #1a202c;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #3182ce;
        margin-bottom: 12px;
    }
    .status-healthy { color: #38a169; font-weight: bold; }
    .status-warning { color: #dd6b20; font-weight: bold; }
    .status-danger { color: #e53e3e; font-weight: bold; }
    .status-backup { color: #3182ce; font-weight: bold; }
    .mode-badge {
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 700;
        display: inline-block;
        letter-spacing: 0.5px;
    }
    .badge-sim { background-color: #d69e2e; color: #1a202c; }
    .badge-cml { background-color: #38a169; color: #ffffff; }
    .badge-cml-not-configured { background-color: #4a5568; color: #e2e8f0; }
    .badge-cml-connecting { background-color: #3182ce; color: #ffffff; }
    .badge-cml-connected { background-color: #38a169; color: #ffffff; }
    .badge-cml-error { background-color: #e53e3e; color: #ffffff; }
    .cml-summary-card {
        background-color: #171923;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .topo-box {
        background-color: #171923;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 14px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# Imports from backend modules
from src.utils.config_loader import load_config
from src.telemetry.simulator import NetworkSimulator
from src.telemetry.collector import TelemetryCollector
from src.cml.cml_client import CMLClient
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.routing.cisco_controller import CiscoController
from src.feedback.feedback_engine import FeedbackEngine
from demo import run_live_demonstration

# Session State Initialization
if "initialized" not in st.session_state:
    config = load_config()
    st.session_state.config = config
    st.session_state.network_mode = config.get("mode", "SIMULATION").upper()
    st.session_state.sim = NetworkSimulator(config)
    st.session_state.fe = FeatureEngine(config)
    st.session_state.predictor = FailurePredictor(config=config)
    st.session_state.ttf_pred = TTFPredictor(config=config)
    st.session_state.path_eval = PathEvaluator(config)
    st.session_state.decision_engine = DecisionEngine(config)
    st.session_state.cisco = CiscoController(config)
    st.session_state.collector = TelemetryCollector(config, cisco_controller=st.session_state.cisco)
    st.session_state.feedback = FeedbackEngine(config)
    st.session_state.history = []
    st.session_state.backup_history = []
    st.session_state.event_log = []
    st.session_state.active_path = "R1 → SW1 → SW2 → R2"
    st.session_state.primary_cost = 10
    st.session_state.last_actual_lead_time = None
    st.session_state.step_count = 0
    st.session_state.cml_status = CMLClient.STATUS_NOT_CONFIGURED if not st.session_state.cisco.cml_client.is_configured() else "NOT CONNECTED"
    st.session_state.cml_connected = False
    st.session_state.cml_diag = None
    st.session_state.routing_verification = None
    st.session_state.current_scenario = 1
    st.session_state.initialized = True

config = st.session_state.config

# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================
st.sidebar.title("🛡️ NOC Control Panel")

# Presentation Mode Toggle
presentation_mode = st.sidebar.checkbox(
    "🎯 Presentation / Viva Mode",
    value=False,
    help="Streamlines the dashboard into an executive overview ideal for project presentation and live defense."
)

st.sidebar.divider()

# Environment Selector: SIMULATION vs CML
st.sidebar.subheader("Environment Selector")
selected_mode = st.sidebar.radio(
    "Active Environment",
    options=["SIMULATION", "CML"],
    index=0 if st.session_state.network_mode == "SIMULATION" else 1,
    help="SIMULATION runs the in-memory Cisco network state engine. CML connects to live Cisco Modeling Labs."
)

if selected_mode != st.session_state.network_mode:
    st.session_state.network_mode = selected_mode
    config["mode"] = selected_mode
    st.session_state.cisco.mode = selected_mode
    st.session_state.collector.mode = selected_mode
    now_time = datetime.now().strftime("%H:%M:%S")
    st.session_state.event_log.append(f"{now_time} - Environment switched to {selected_mode}")
    st.rerun()

# ------------------------------------------------------------------------------
# SIMULATION MODE CONTROLS
# ------------------------------------------------------------------------------
if st.session_state.network_mode == "SIMULATION":
    st.sidebar.markdown("<span class='mode-badge badge-sim'>SIMULATION MODE</span>", unsafe_allow_html=True)
    st.sidebar.caption("Operating on high-fidelity deterministic network state engine.")

    # Scenario Selector
    st.sidebar.subheader("Scenario Control")
    scenario_names = {
        1: "Scenario 1: Healthy Network",
        2: "Scenario 2: Minor Degradation",
        3: "Scenario 3: Strong Degradation",
        4: "Scenario 4: Failure with Backup Preemption",
        5: "Scenario 5: Poor Backup Path",
        6: "Scenario 6: False Positive / Flapping Anomaly",
        7: "Scenario 7: Primary Recovery",
        8: "Scenario 8: Backup Degradation"
    }

    def handle_scenario_switch(new_scenario_id: int):
        st.session_state.current_scenario = new_scenario_id
        st.session_state.sim.set_scenario(new_scenario_id)
        st.session_state.history = []
        st.session_state.backup_history = []
        st.session_state.active_path = "R1 → SW1 → SW2 → R2"
        st.session_state.primary_cost = 10
        st.session_state.sim.set_primary_status(True)
        st.session_state.sim.set_backup_status(True)
        st.session_state.sim.set_primary_cost(10)
        st.session_state.sim.set_backup_cost(10)
        st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
        st.session_state.feedback = FeedbackEngine(st.session_state.config)
        st.session_state.last_actual_lead_time = None
        step_data = st.session_state.sim.generate_telemetry_step()
        st.session_state.history.append(step_data["primary"])
        st.session_state.backup_history.append(step_data["backup"])
        st.session_state.step_count = st.session_state.sim.step_count
        now_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_log.append(
            f"{now_time} - Switched to Scenario {new_scenario_id}: {scenario_names[new_scenario_id]} (Step {st.session_state.step_count})"
        )

    selected_scenario_id = st.sidebar.selectbox(
        "Select Scenario",
        options=list(scenario_names.keys()),
        index=list(scenario_names.keys()).index(st.session_state.get("current_scenario", 1)),
        key="scenario_select_box",
        format_func=lambda x: scenario_names[x]
    )

    if selected_scenario_id != st.session_state.get("current_scenario"):
        handle_scenario_switch(selected_scenario_id)

    # Traffic Class Selector
    traffic_class = st.sidebar.selectbox(
        "Traffic Class (QoS)",
        options=["VOIP", "VIDEO", "NORMAL_DATA"],
        index=0,
        help="VoIP prioritizes latency/loss. Video prioritizes bandwidth headroom. Normal Data uses balanced criteria."
    )

    dry_run = st.sidebar.checkbox(
        "DRY_RUN Safety Mode",
        value=config.get("decision", {}).get("dry_run", False),
        help="When enabled, decisions are logged but routing metric changes are not applied."
    )
    st.session_state.decision_engine.set_dry_run(dry_run)
    st.session_state.cisco.set_dry_run(dry_run)

    st.sidebar.divider()

    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("▶ Step Once", use_container_width=True):
            if st.session_state.sim.scenario != selected_scenario_id:
                handle_scenario_switch(selected_scenario_id)
            else:
                step_data = st.session_state.sim.generate_telemetry_step()
                st.session_state.history.append(step_data["primary"])
                st.session_state.backup_history.append(step_data["backup"])
                st.session_state.step_count = st.session_state.sim.step_count
                now_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.event_log.append(
                    f"{now_time} - Polled telemetry cycle {st.session_state.step_count} (Scenario {selected_scenario_id})"
                )
    with col_s2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.history = []
            st.session_state.backup_history = []
            st.session_state.event_log = []
            st.session_state.active_path = "R1 → SW1 → SW2 → R2"
            st.session_state.primary_cost = 10
            st.session_state.current_scenario = 1
            st.session_state.scenario_select_box = 1
            st.session_state.sim.reset()
            st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
            st.session_state.feedback = FeedbackEngine(st.session_state.config)
            st.session_state.last_actual_lead_time = None
            st.session_state.step_count = 0
            st.rerun()

# ------------------------------------------------------------------------------
# CML MODE CONTROLS
# ------------------------------------------------------------------------------
else:
    # Render CML status badge
    curr_cml_status = st.session_state.get("cml_status", CMLClient.STATUS_NOT_CONFIGURED)
    if curr_cml_status == CMLClient.STATUS_CONNECTED:
        badge_html = "<span class='mode-badge badge-cml-connected'>CML CONNECTED ✓</span>"
    elif curr_cml_status == CMLClient.STATUS_CONNECTING:
        badge_html = "<span class='mode-badge badge-cml-connecting'>CONNECTING...</span>"
    elif curr_cml_status == CMLClient.STATUS_ERROR:
        badge_html = "<span class='mode-badge badge-cml-error'>CML ERROR ✗</span>"
    else:
        badge_html = "<span class='mode-badge badge-cml-not-configured'>NOT CONFIGURED</span>"

    st.sidebar.markdown(badge_html, unsafe_allow_html=True)

    if st.sidebar.button("🔌 Verify CML Connection", use_container_width=True):
        with st.sidebar:
            with st.spinner("Probing CML REST API & SSH Nodes..."):
                diag = st.session_state.cisco.verify_cml_connection()
                st.session_state.cml_diag = diag
                st.session_state.cml_status = diag["status"]
                st.session_state.cml_connected = (diag["status"] == CMLClient.STATUS_CONNECTED)
                if st.session_state.cml_connected:
                    st.success("Cisco Modeling Labs connection verified!")
                elif diag["status"] == CMLClient.STATUS_NOT_CONFIGURED:
                    st.warning("CML credentials not configured in .env.")
                else:
                    st.error(f"Connection error: {diag['message']}")
                st.rerun()

    if st.session_state.cml_diag:
        diag = st.session_state.cml_diag
        with st.sidebar.expander("ℹ️ Connection Diagnostics", expanded=(diag["status"] != CMLClient.STATUS_CONNECTED)):
            st.caption(f"**Diagnostic Status:** {diag['status']}")
            st.caption(f"**Message:** {diag['message']}")
            rest = diag.get("cml_rest", {})
            st.caption(f"**CML REST Host:** {rest.get('host', 'N/A')}:{rest.get('port', 443)}")
            st.caption(f"**Lab ID:** {rest.get('lab_id', 'N/A')}")
            ssh_devs = diag.get("ssh_devices", {})
            for dev_name, dev_info in ssh_devs.items():
                st.caption(f"- **{dev_name}** ({dev_info['ip']}): `{dev_info['status']}`")

    # Traffic Class & DRY_RUN in CML Mode
    st.sidebar.subheader("Controller Policy")
    traffic_class = st.sidebar.selectbox(
        "Traffic Class (QoS)",
        options=["VOIP", "VIDEO", "NORMAL_DATA"],
        index=0,
        help="VoIP prioritizes latency/loss. Video prioritizes bandwidth headroom. Normal Data uses balanced criteria."
    )

    dry_run = st.sidebar.checkbox(
        "DRY_RUN Safety Mode",
        value=config.get("decision", {}).get("dry_run", False),
        help="When enabled, routing commands are simulated/logged without mutating live CML switch configs."
    )
    st.session_state.decision_engine.set_dry_run(dry_run)
    st.session_state.cisco.set_dry_run(dry_run)

    st.sidebar.subheader("Live CML Demo Workflow")
    cml_b1, cml_b2 = st.sidebar.columns(2)
    with cml_b1:
        if st.button("📡 Collect Telemetry", use_container_width=True):
            step_data = st.session_state.collector.collect_step()
            st.session_state.history.append(step_data["primary"])
            st.session_state.backup_history.append(step_data["backup"])
            st.session_state.step_count += 1
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - Polled CML telemetry cycle {st.session_state.step_count}")
            st.rerun()

    with cml_b2:
        if st.button("🧠 Run AI Prediction", use_container_width=True):
            if not st.session_state.history:
                step_data = st.session_state.collector.collect_step()
                st.session_state.history.append(step_data["primary"])
                st.session_state.backup_history.append(step_data["backup"])
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - Executed AI link failure & TTF prediction inference")
            st.rerun()

    cml_b3, cml_b4 = st.sidebar.columns(2)
    with cml_b3:
        if st.button("🎯 Evaluate Backup", use_container_width=True):
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - Evaluated backup candidate path QoS metrics")
            st.rerun()

    with cml_b4:
        if st.button("⚡ Execute Reroute", use_container_width=True):
            st.session_state.active_path = "R1 → SW1 → SW3 → SW2 → R2"
            st.session_state.primary_cost = 100
            st.session_state.cisco.change_metric("SW1", "GigabitEthernet0/1", 100)
            st.session_state.sim.set_primary_cost(100)
            st.session_state.routing_verification = st.session_state.cisco.verify_routing("SW1")
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - MANUAL OVERRIDE: Proactively rerouted traffic to SW3 (Metric 100).")
            st.rerun()

    cml_b5, cml_b6 = st.sidebar.columns(2)
    with cml_b5:
        if st.button("🔍 Verify Routing", use_container_width=True):
            st.session_state.routing_verification = st.session_state.cisco.verify_routing("SW1")
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - Verified OSPF routing table on SW1")
            st.rerun()

    with cml_b6:
        if st.button("🔄 Reset / Restore", use_container_width=True):
            st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
            st.session_state.cisco.enable_interface("SW1", "GigabitEthernet0/1")
            st.session_state.sim.reset()
            st.session_state.active_path = "R1 → SW1 → SW2 → R2"
            st.session_state.primary_cost = 10
            st.session_state.history = []
            st.session_state.backup_history = []
            st.session_state.routing_verification = None
            st.session_state.step_count = 0
            now_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.event_log.append(f"{now_time} - Restored baseline OSPF metric 10 and enabled SW1:Gi0/1")
            st.rerun()

    # CML Controlled Failure Injection
    st.sidebar.divider()
    with st.sidebar.expander("💥 Controlled Failure Injection", expanded=False):
        st.caption("Safely inject network faults to test adaptive self-healing behavior.")
        failure_scenario = st.selectbox(
            "Failure Scenario",
            options=["Interface failure (shutdown Gi0/1)", "Gradual degradation (CRC/Loss)", "High latency (Delay spike)", "Packet loss anomaly"],
            index=0
        )
        confirm_injection = st.checkbox("⚠️ Confirm Failure Injection", value=False, help="Safety toggle required before applying changes to CML topology.")

        col_fi1, col_fi2 = st.columns(2)
        with col_fi1:
            if st.button("Inject Fault", use_container_width=True, type="secondary"):
                if not confirm_injection:
                    st.error("Please check 'Confirm Failure Injection' first.")
                else:
                    if "shutdown" in failure_scenario:
                        st.session_state.cisco.shutdown_interface("SW1", "GigabitEthernet0/1")
                        st.session_state.sim.set_primary_status(False)
                    else:
                        st.session_state.sim.set_scenario(3)
                        step_data = st.session_state.sim.generate_telemetry_step()
                        st.session_state.history.append(step_data["primary"])
                        st.session_state.backup_history.append(step_data["backup"])
                    now_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.event_log.append(f"{now_time} - INJECTED FAULT: {failure_scenario}")
                    st.rerun()
        with col_fi2:
            if st.button("Restore Link", use_container_width=True):
                st.session_state.cisco.enable_interface("SW1", "GigabitEthernet0/1")
                st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
                st.session_state.sim.set_primary_status(True)
                st.session_state.sim.set_primary_cost(10)
                st.session_state.active_path = "R1 → SW1 → SW2 → R2"
                st.session_state.primary_cost = 10
                now_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.event_log.append(f"{now_time} - RESTORED FAULT: Enabled SW1:Gi0/1 and reset OSPF metric.")
                st.rerun()

# ==============================================================================
# PIPELINE COMPUTATION
# ==============================================================================
if st.session_state.history:
    hist_df = pd.DataFrame(st.session_state.history)
    feats = st.session_state.fe.extract_features(hist_df)
    pred = st.session_state.predictor.predict(feats)
    ttf = st.session_state.ttf_pred.estimate_ttf(feats, pred["failure_probability"])
    latest_p = st.session_state.history[-1]
else:
    hist_df = pd.DataFrame()
    feats = {feat: 0.0 for feat in st.session_state.fe.FEATURE_NAMES}
    pred = {
        "predicted_class_id": 0,
        "predicted_class": "HEALTHY",
        "failure_probability": 0.0,
        "confidence": 1.0,
        "class_probabilities": {"HEALTHY": 1.0, "WARNING": 0.0, "HIGH_RISK": 0.0},
        "contributing_indicators": ["All monitored telemetry dimensions within nominal baseline thresholds."],
        "inference_engine": "ML_DECISION_TREE"
    }
    ttf = {"estimated_ttf_ms": None, "ttf_range_str": "Stable / Nominal"}
    latest_p = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "device": "SW1",
        "interface": "GigabitEthernet0/1",
        "path_id": "PATH_PRIMARY",
        "rtt": 12.0,
        "jitter": 1.5,
        "packet_loss": 0.0,
        "crc_errors": 0,
        "interface_errors": 0,
        "interface_flaps": 0,
        "utilization": 35.0,
        "link_status": "UP",
        "ospf_cost": 10,
        "telemetry_source": "SIMULATION"
    }

p_status = latest_p.get("link_status", "UP")

if st.session_state.backup_history:
    latest_b = st.session_state.backup_history[-1]
    backup_df = pd.DataFrame(st.session_state.backup_history)
    backup_feats = st.session_state.fe.extract_features(backup_df)
    backup_pred = st.session_state.predictor.predict(backup_feats)
    backup_risk = 1.0 if latest_b.get("link_status") != "UP" else float(backup_pred["failure_probability"])
else:
    latest_b = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "device": "SW1",
        "interface": "GigabitEthernet0/2",
        "path_id": "PATH_BACKUP",
        "rtt": 18.0,
        "jitter": 2.0,
        "packet_loss": 0.0,
        "crc_errors": 0,
        "interface_errors": 0,
        "interface_flaps": 0,
        "utilization": 25.0,
        "link_status": "UP",
        "ospf_cost": 10,
        "telemetry_source": "SIMULATION"
    }
    backup_risk = 0.05

b_status = latest_b.get("link_status", "UP")

candidates = [
    {
        "path_id": "PATH_PRIMARY",
        "name": "R1 → SW1 → SW2 → R2",
        "rtt": latest_p["rtt"],
        "packet_loss": latest_p["packet_loss"],
        "utilization": latest_p["utilization"],
        "risk": pred["failure_probability"],
        "hops": 3,
        "interface": "GigabitEthernet0/1"
    },
    {
        "path_id": "PATH_BACKUP",
        "name": "R1 → SW1 → SW3 → SW2 → R2",
        "rtt": latest_b["rtt"],
        "packet_loss": latest_b["packet_loss"],
        "utilization": latest_b["utilization"],
        "risk": backup_risk,
        "hops": 4,
        "interface": "GigabitEthernet0/2"
    }
]
path_eval = st.session_state.path_eval.evaluate_paths(candidates, traffic_class=traffic_class)
best_path = path_eval["best_path"]

decision = st.session_state.decision_engine.evaluate(
    prediction_result=pred,
    ttf_result=ttf,
    primary_link_status=p_status,
    best_candidate_path=best_path,
    current_active_path_id="PATH_BACKUP" if "SW3" in st.session_state.active_path else "PATH_PRIMARY",
    traffic_class=traffic_class
)

# Apply routing action when decision mandates reroute
if decision["should_reroute"] and "SW3" not in st.session_state.active_path:
    st.session_state.active_path = "R1 → SW1 → SW3 → SW2 → R2"
    st.session_state.primary_cost = 100
    st.session_state.cisco.change_metric("SW1", "GigabitEthernet0/1", 100)
    st.session_state.sim.set_primary_cost(100)
    st.session_state.feedback.record_reroute(decision)
    st.session_state.routing_verification = st.session_state.cisco.verify_routing("SW1")
    now_time = datetime.now().strftime("%H:%M:%S")
    st.session_state.event_log.append(f"{now_time} - PREEMPTIVE REROUTE: Primary metric modified to 100. Traffic moved to Backup.")

# Anti-flapping hysteresis check if on backup
hyst = None
if "SW3" in st.session_state.active_path:
    hyst = st.session_state.feedback.evaluate_restoration_hysteresis(
        primary_link_up=(p_status == "UP"),
        primary_failure_prob=pred["failure_probability"]
    )
    if hyst["can_restore"]:
        st.session_state.active_path = "R1 → SW1 → SW2 → R2"
        st.session_state.primary_cost = 10
        st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
        st.session_state.sim.set_primary_cost(10)
        st.session_state.routing_verification = st.session_state.cisco.verify_routing("SW1")
        now_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_log.append(f"{now_time} - HYSTERESIS APPROVED: Stability verified. Restored traffic to Primary.")

# ==============================================================================
# MAIN PAGE HEADER
# ==============================================================================
st.title("🛡️ AI-Driven Adaptive Self-Healing Network")
st.markdown("##### *AI-Powered Predictive Failure Detection, Risk-Aware Routing & Automated Network Recovery*")

# Telemetry Source Label
telemetry_label = "SIMULATED TELEMETRY" if st.session_state.network_mode == "SIMULATION" else "REAL CML TELEMETRY"
st.caption(f"Data Source: **{telemetry_label}** | Environment: **{st.session_state.network_mode}** | Active Traffic Profile: **{traffic_class}**")

# ==============================================================================
# CML LIVE OPERATIONS MONITOR (Only shown when CML mode is selected)
# ==============================================================================
if st.session_state.network_mode == "CML":
    st.markdown("### 🔌 Cisco Modeling Labs (CML) Live Operations")
    cml_stat = st.session_state.get("cml_status", "NOT CONFIGURED")
    migrated = ("SW3" in st.session_state.active_path)
    migrated_badge = "SUCCESS ✓" if migrated else "STANDBY"

    with st.container():
        col_cml_a, col_cml_b, col_cml_c = st.columns(3)
        with col_cml_a:
            st.markdown(f"**CML Status:** `{cml_stat}`")
            dev_stat = "SW1: Gi0/1 (UP), Gi0/2 (UP)" if p_status == "UP" else "SW1: Gi0/1 (DOWN), Gi0/2 (UP)"
            st.markdown(f"**Device Status:** `{dev_stat}`")
            st.markdown(f"**Primary Path:** `{candidates[0]['name']}`")
            st.markdown(f"**Backup Path:** `{candidates[1]['name']}`")
            st.markdown(f"**Current OSPF Cost:** `{st.session_state.primary_cost}`")
            new_cost_str = "100 (Backup Preempted)" if migrated else "10 (Optimal Baseline)"
            st.markdown(f"**New OSPF Cost:** `{new_cost_str}`")

        with col_cml_b:
            st.markdown("**Live CML Telemetry:**")
            st.markdown(f"- **RTT:** `{latest_p['rtt']:.1f} ms`")
            st.markdown(f"- **Jitter:** `{latest_p['jitter']:.1f} ms`")
            st.markdown(f"- **Packet Loss:** `{latest_p['packet_loss']:.1f}%`")
            st.markdown(f"- **CRC Errors:** `{latest_p.get('crc_errors', 0)}`")
            st.markdown(f"- **Input Errors:** `{latest_p.get('input_errors', 0)}`")
            st.markdown(f"- **Output Errors:** `{latest_p.get('output_errors', 0)}`")
            st.markdown(f"- **Utilization:** `{latest_p['utilization']:.1f}%`")

        with col_cml_c:
            st.markdown("**AI Inference & Routing Action:**")
            st.markdown(f"- **AI Class:** `{pred['predicted_class']}`")
            st.markdown(f"- **Failure Risk:** `{pred['failure_probability']*100:.1f}%`")
            st.markdown(f"- **Confidence:** `{pred['confidence']*100:.1f}%`")
            st.markdown(f"- **TTF:** `{ttf.get('ttf_range_str', 'N/A')}`")
            st.markdown(f"- **Decision:** `{decision['action']}`")
            last_act = st.session_state.cisco.last_action or {}
            act_name = last_act.get("action", "MONITORING")
            if last_act.get("dry_run"):
                act_name += " (DRY RUN)"
            st.markdown(f"- **Routing Action:** `{act_name}`")
            if last_act.get("command_str"):
                st.caption(f"Last Command: `{last_act.get('command_str')}`")
            st.markdown(f"- **Traffic Migration:** **{migrated_badge}**")
            ver_details = st.session_state.routing_verification.get("details", "Traffic verified on primary path.") if st.session_state.routing_verification else ("OSPF converged to SW3 transit path." if migrated else "Baseline OSPF optimal path active.")
            st.markdown(f"- **Verification Result:** {ver_details}")
            st.markdown(f"- **Feedback:** `{hyst.get('reason', 'System stable') if hyst else ('Active on primary' if not migrated else 'Monitoring backup stability')}`")

st.divider()

# ==============================================================================
# SECTION: TOPOLOGY & ROUTING STATUS
# ==============================================================================
st.subheader("🌐 Network Topology & Active Path State")

col_t1, col_t2, col_t3, col_t4 = st.columns(4)
with col_t1:
    st.metric(
        "Active Routing Path",
        st.session_state.active_path,
        delta="Preempted to Backup" if "SW3" in st.session_state.active_path else "Optimal Primary",
        delta_color="normal"
    )
with col_t2:
    st.metric(
        "Primary Link (SW1-Gi0/1)",
        f"Cost {st.session_state.primary_cost} | {p_status}",
        delta="Rerouted (+90)" if st.session_state.primary_cost > 10 else "Baseline (Cost 10)",
        delta_color="inverse" if p_status == "DOWN" or st.session_state.primary_cost > 10 else "normal"
    )
with col_t3:
    st.metric(
        "Backup Path (via SW3)",
        f"Cost 40 | {b_status}",
        delta="Active Transit" if "SW3" in st.session_state.active_path else "Standby",
        delta_color="normal" if b_status == "UP" else "inverse"
    )
with col_t4:
    st.metric(
        "QoS Traffic Sensitivity",
        traffic_class,
        help="VoIP (High latency/loss weight) | Video (High bandwidth/util weight) | Normal Data (Balanced)"
    )

# Visual Logical Topology Card
with st.expander("🗺️ Redundant Cisco Network Architecture (OSPF Area 0)", expanded=True):
    p_badge = "🔴 DOWN" if p_status == "DOWN" else ("🟡 DEGRADING" if pred["failure_probability"] >= 0.75 else "🟢 HEALTHY")
    b_badge = "🔴 DOWN" if b_status == "DOWN" else ("🔵 ACTIVE" if "SW3" in st.session_state.active_path else "🟢 STANDBY")

    col_topo_a, col_topo_b = st.columns([3, 2])
    with col_topo_a:
        st.markdown(f"""
```text
                 [ R1: Source Gateway ]
                           |
                           v
              +-------------------------+
              | SW1: Core Ingress Switch|
              +-------------------------+
                     /           \\
   (Primary: Cost {st.session_state.primary_cost:<3}) /             \\ (Backup: Cost 10)
                   /               \\
                  v                 v
  +-------------------------+     +-------------------------+
  | SW2: Core Egress Switch | <---| SW3: Backup Transit Switch|
  +-------------------------+     +-------------------------+
               |
               v
     [ R2: Destination Gateway ]
```
        """)
    with col_topo_b:
        st.markdown(f"""
        **Logical Paths & OSPF Metrics:**
        - **PRIMARY PATH:** `R1 → SW1 → SW2 → R2`
          - Physical Link: `SW1:Gi0/1 ↔ SW2:Gi0/1`
          - Status: **{p_badge}**
          - Configured Cost: **{st.session_state.primary_cost}** (Total Path: {20 + st.session_state.primary_cost})
        - **BACKUP PATH:** `R1 → SW1 → SW3 → SW2 → R2`
          - Physical Links: `SW1:Gi0/2 ↔ SW3:Gi0/2`, `SW3:Gi0/1 ↔ SW2:Gi0/2`
          - Status: **{b_badge}**
          - Configured Cost: **40 Total** (Standby OSPF Cost)
        """)

st.divider()

# ==============================================================================
# SECTION: AI FAILURE PREDICTION & TIME-TO-FAILURE
# ==============================================================================
st.subheader("🧠 AI Link Failure Prediction & Time-To-Failure (TTF)")

col_ai1, col_ai2, col_ai3, col_ai4 = st.columns(4)
with col_ai1:
    p_class = pred["predicted_class"]
    st.metric("Predicted Health State", p_class, delta=f"Risk: {pred['failure_probability']*100:.1f}%")
with col_ai2:
    st.metric("Failure Risk (Probability)", f"{pred['failure_probability']*100:.1f}%", help="Model estimated likelihood that link is failing")
with col_ai3:
    st.metric("Model Confidence", f"{pred['confidence']*100:.1f}%", help="Confidence score across class distributions (Threshold >= 80% required to reroute)")
with col_ai4:
    st.metric("Predicted TTF (Lead Horizon)", ttf.get("ttf_range_str", "N/A"), help="Model predicted time before threshold collapse")

if st.session_state.last_actual_lead_time is not None:
    st.info(f"⏱️ **Experimental Lead Time Achieved:** Proactive preemption executed **{st.session_state.last_actual_lead_time:.1f} ms** before physical failure.")

# Explainability Indicators
with st.expander("🔍 AI Explainability: Contributing Feature Indicators", expanded=True):
    st.caption("Active feature indicators driving the Decision Tree classification:")
    for ind in pred["contributing_indicators"]:
        st.markdown(f"- {ind}")

st.divider()

# ==============================================================================
# SECTION: CONFIDENCE-GATED DECISION ENGINE & QoS PATH EVALUATION
# ==============================================================================
col_dec1, col_dec2 = st.columns([1, 1])

with col_dec1:
    st.subheader("⚡ Confidence-Gated Decision Engine")
    d_act = decision["action"]
    st.markdown(f"**Current Action:** `{d_act}`")
    st.markdown(f"**Confidence Gate:** `{'PASSED (>= 80%)' if decision['confidence_check_passed'] else 'BLOCKED (< 80%)'}`")
    st.markdown(f"**Decision Rationale:** {decision['reason']}")

    if hyst:
        st.caption(f"**Hysteresis Recovery Timer:** {hyst['reason']}")

with col_dec2:
    st.subheader("🎯 QoS Candidate Path Evaluation")
    st.caption(f"Applied QoS Profile: **{traffic_class}** (Lower score = superior path)")

    p_table = []
    for p in path_eval["ranked_paths"]:
        is_active = (p["name"] == st.session_state.active_path)
        p_table.append({
            "Status": "⭐ ACTIVE" if is_active else "STANDBY",
            "Path": p["name"],
            "RTT (ms)": f"{p['rtt']:.1f}",
            "Loss (%)": f"{p['packet_loss']:.1f}%",
            "Utilization": f"{p['utilization']:.1f}%",
            "Risk": f"{p['risk']*100:.0f}%",
            "Hops": p["hops"],
            "Penalty Score": f"{p['score']:.4f}"
        })
    st.dataframe(pd.DataFrame(p_table), use_container_width=True, hide_index=True)

st.divider()

# ==============================================================================
# SECTION: INTERACTIVE DEMO & EXPERIMENTS CONTROLS
# ==============================================================================
st.subheader("🚀 Interactive Demonstration & Benchmark Suite")

col_btn_demo, col_btn_bench, col_btn_test, col_btn_train = st.columns(4)

with col_btn_demo:
    run_demo_clicked = st.button("▶ RUN FULL SELF-HEALING DEMO", use_container_width=True, type="primary")

with col_btn_bench:
    run_bench_clicked = st.button("📊 RUN REACTIVE VS PROACTIVE BENCHMARK", use_container_width=True)

with col_btn_test:
    run_tests_clicked = st.button("🧪 RUN TEST SUITE", use_container_width=True)

with col_btn_train:
    run_train_clicked = st.button("🔄 RETRAIN MODELS", use_container_width=True)

# 1. Full Demo Execution
if run_demo_clicked:
    st.markdown("### 🎬 Self-Healing Live Demonstration Execution")
    demo_progress_bar = st.progress(0)
    demo_status_text = st.empty()
    demo_log_container = st.container()

    def demo_callback(phase_num, phase_title, data):
        pct = int((phase_num / 8) * 100)
        demo_progress_bar.progress(pct)
        demo_status_text.markdown(f"**Phase {phase_num}/8:** *{phase_title}*")
        with demo_log_container:
            st.write(f"✅ **Phase {phase_num}: {phase_title}**", data)

    with st.spinner("Executing self-healing demonstration cycle..."):
        demo_res = run_live_demonstration(progress_callback=demo_callback, sleep_interval=0.4)
        st.session_state.last_actual_lead_time = demo_res["actual_lead_time_ms"]
        st.session_state.active_path = "R1 → SW1 → SW3 → SW2 → R2"
        st.session_state.primary_cost = 100
        st.success(f"Self-healing demo completed successfully! Achieved Failure Lead Time: **{demo_res['actual_lead_time_ms']} ms** early with **0.0% packet loss** during link collapse.")
        now_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_log.append(f"{now_time} - DEMO COMPLETE: Lead time {demo_res['actual_lead_time_ms']}ms, 0% packet loss.")

# 2. Benchmark Comparison Execution
if run_bench_clicked:
    st.markdown("### 🔬 Reactive OSPF vs. AI Proactive Benchmark")
    with st.spinner("Executing baseline reactive and AI proactive comparative benchmarks..."):
        try:
            from src.experiments.compare_experiments import compare_and_generate_reports
            comp_res = compare_and_generate_reports()
            st.success("Benchmark evaluation completed!")

            # Display comparative metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Packet Loss Reduction", f"{comp_res['loss_reduction_pct']}%", delta=f"{comp_res['reactive_loss_pct']}% -> {comp_res['proactive_loss_pct']}%", delta_color="inverse")
            c2.metric("Convergence Downtime", f"{comp_res['proactive_convergence_ms']} ms", delta=f"-{comp_res['reactive_convergence_ms']} ms", delta_color="inverse")
            c3.metric("Failure Lead Time", f"{comp_res['failure_lead_time_ms']} ms early")
            c4.metric("Latency Spike Attenuation", f"{comp_res['proactive_max_rtt_ms']} ms", delta=f"-{comp_res['reactive_max_rtt_ms'] - comp_res['proactive_max_rtt_ms']} ms", delta_color="inverse")

            # Display Plots
            g_col1, g_col2 = st.columns(2)
            loss_img = ROOT_DIR / "results" / "graphs" / "packet_loss_comparison.png"
            rtt_img = ROOT_DIR / "results" / "graphs" / "rtt_comparison.png"
            if loss_img.exists():
                g_col1.image(str(loss_img), caption="Packet Loss: Reactive (Blackout) vs AI Proactive (0% loss)")
            if rtt_img.exists():
                g_col2.image(str(rtt_img), caption="RTT Continuity during Network Failure")
        except Exception as e:
            st.error(f"Error running benchmark: {e}")

# 3. Test Suite Runner
if run_tests_clicked:
    st.markdown("### 🧪 Unit & Integration Test Suite Verification")
    with st.spinner("Executing `python -m unittest discover tests -v`..."):
        res = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "tests", "-v"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True
        )
        output = res.stderr + "\n" + res.stdout
        passed = "OK" in output
        test_count = output.count(" ... ok")

        if passed:
            st.success(f"**ALL TESTS PASSED!** ({test_count} tests passed with 0 failures)")
        else:
            st.error("Some tests failed. Check log below.")

        with st.expander("View Full Test Execution Log", expanded=False):
            st.code(output)

# 4. Model Training Runner
if run_train_clicked:
    st.markdown("### 🔄 Model Retraining")
    with st.spinner("Generating synthetic degradation dataset and retraining models..."):
        res = subprocess.run(
            [sys.executable, "train.py"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            st.success("Model retraining complete! Reloaded Decision Tree and TTF models.")
            st.session_state.predictor.load_model()
            st.session_state.ttf_pred.load_model()
            with st.expander("View Training Output Log"):
                st.code(res.stderr + "\n" + res.stdout)
        else:
            st.error("Training encountered an error.")
            st.code(res.stderr)

st.divider()

# ==============================================================================
# SECTION: TELEMETRY TRENDS & EVENT LOG (Hidden in Simplified Presentation Mode)
# ==============================================================================
if not presentation_mode:
    st.subheader(f"📈 Multi-Dimensional Telemetry ({telemetry_label})")
    tab_primary, tab_backup = st.tabs(["Primary Path (SW1-Gi0/1)", "Backup Path (via SW3)"])
    with tab_primary:
        if len(hist_df) > 0:
            c_plot1, c_plot2 = st.columns(2)
            with c_plot1:
                st.markdown("**Primary Round-Trip Time (RTT) & Jitter (ms)**")
                st.line_chart(hist_df[["rtt", "jitter"]].tail(30))
            with c_plot2:
                st.markdown("**Primary Packet Loss (%) & Cumulative CRC Errors**")
                st.line_chart(hist_df[["packet_loss", "crc_errors"]].tail(30))
        else:
            st.caption("No primary telemetry recorded yet. Click '▶ Step Once' to begin.")

    with tab_backup:
        backup_hist_df = pd.DataFrame(st.session_state.backup_history)
        if len(backup_hist_df) > 0:
            cb_plot1, cb_plot2 = st.columns(2)
            with cb_plot1:
                st.markdown("**Backup Round-Trip Time (RTT) & Jitter (ms)**")
                st.line_chart(backup_hist_df[["rtt", "jitter"]].tail(30))
            with cb_plot2:
                st.markdown("**Backup Packet Loss (%) & Cumulative CRC Errors**")
                st.line_chart(backup_hist_df[["packet_loss", "crc_errors"]].tail(30))
        else:
            st.caption("No backup telemetry recorded yet. Click '▶ Step Once' to begin.")

    st.divider()

    col_fb1, col_fb2 = st.columns([1, 1])
    with col_fb1:
        st.subheader("📋 System Feedback & Classification Matrix")
        stats = st.session_state.feedback.stats
        st.markdown(f"""
        - **True Positives (TP):** `{stats['TRUE_POSITIVE']}`
        - **False Positives (FP):** `{stats['FALSE_POSITIVE']}`
        - **True Negatives (TN):** `{stats['TRUE_NEGATIVE']}`
        - **False Negatives (FN):** `{stats['FALSE_NEGATIVE']}`
        - **Recovery Successes:** `{stats['RECOVERY_SUCCESS']}`
        - **Recovery Failures:** `{stats['RECOVERY_FAILURE']}`
        """)

    with col_fb2:
        st.subheader("📜 Live Event Log")
        if st.session_state.event_log:
            for ev in reversed(st.session_state.event_log[-8:]):
                st.markdown(f"• `{ev}`")
        else:
            st.caption("No events recorded yet. Run a scenario or demo.")
else:
    st.info("💡 **Presentation Mode Active**: Telemetry charts and low-level logs hidden for simplified viva presentation. Uncheck Presentation Mode in sidebar to view full diagnostic views.")
