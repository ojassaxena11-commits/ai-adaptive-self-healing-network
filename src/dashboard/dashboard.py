import os
import time
import json
import pandas as pd
import streamlit as st

# Configure Streamlit Page
st.set_page_config(
    page_title="AI-Driven Self-Healing Network NOC",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Dark Modern NOC Theme
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2530;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #3498db;
        margin-bottom: 10px;
    }
    .status-healthy { color: #2ecc71; font-weight: bold; }
    .status-warning { color: #f39c12; font-weight: bold; }
    .status-danger { color: #e74c3c; font-weight: bold; }
    .status-backup { color: #3498db; font-weight: bold; }
    .mode-badge {
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: bold;
        display: inline-block;
    }
    .badge-sim { background-color: #f39c12; color: #111; }
    .badge-cml { background-color: #2ecc71; color: #111; }
</style>
""", unsafe_allow_html=True)

# Imports from src
from src.utils.config_loader import load_config
from src.telemetry.simulator import NetworkSimulator
from src.features.feature_engine import FeatureEngine
from src.prediction.failure_predictor import FailurePredictor
from src.prediction.ttf_predictor import TTFPredictor
from src.decision.decision_engine import DecisionEngine
from src.routing.path_evaluator import PathEvaluator
from src.routing.cisco_controller import CiscoController
from src.feedback.feedback_engine import FeedbackEngine

# Initialize Session State
if "initialized" not in st.session_state:
    config = load_config()
    st.session_state.config = config
    st.session_state.sim = NetworkSimulator(config)
    st.session_state.fe = FeatureEngine(config)
    st.session_state.predictor = FailurePredictor(config=config)
    st.session_state.ttf_pred = TTFPredictor(config=config)
    st.session_state.path_eval = PathEvaluator(config)
    st.session_state.decision_engine = DecisionEngine(config)
    st.session_state.cisco = CiscoController(config)
    st.session_state.feedback = FeedbackEngine(config)
    st.session_state.history = []
    st.session_state.active_path = "PATH_PRIMARY"
    st.session_state.primary_cost = 10
    st.session_state.auto_run = False
    st.session_state.step_counter = 0
    st.session_state.initialized = True

config = st.session_state.config
mode = config.get("mode", "SIMULATION").upper()

# Sidebar Controls
st.sidebar.title("🛡️ NOC Control Panel")
st.sidebar.markdown(f"**Operating Mode:** <span class='mode-badge {'badge-cml' if mode=='CML' else 'badge-sim'}'>{mode}</span>", unsafe_allow_html=True)
if mode == "SIMULATION":
    st.sidebar.caption("High-fidelity mathematical emulation active.")
else:
    st.sidebar.caption("Live Cisco Modeling Labs (CML) API/SSH connected.")

st.sidebar.divider()

scenario_id = st.sidebar.selectbox(
    "Select Network Scenario",
    options=[
        (1, "Scenario 1: Healthy Network (Baseline)"),
        (2, "Scenario 2: Minor Temporary Jitter (Noise)"),
        (3, "Scenario 3: Strong Degradation (Incipient Failure)"),
        (4, "Scenario 4: Predicted Failure + Good Backup (Preemption)"),
        (5, "Scenario 5: Predicted Failure + Congested Backup"),
        (6, "Scenario 6: False Alarm / Flapping Anomaly"),
        (7, "Scenario 7: Primary Recovery & Hysteresis"),
        (8, "Scenario 8: Backup Degradation")
    ],
    format_func=lambda x: x[1]
)[0]

traffic_class = st.sidebar.selectbox(
    "Application Traffic Class (QoS)",
    options=["VOIP", "VIDEO", "NORMAL_DATA"],
    index=0
)

dry_run = st.sidebar.checkbox("DRY_RUN Safety Mode", value=config.get("decision", {}).get("dry_run", False))
st.session_state.decision_engine.set_dry_run(dry_run)
st.session_state.cisco.set_dry_run(dry_run)

st.sidebar.divider()
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("▶ Step Once"):
        st.session_state.sim.set_scenario(scenario_id)
        # Advance 1 step
        t = st.session_state.sim.generate_telemetry_step()
        st.session_state.history.append(t["primary"])
        st.session_state.step_counter += 1
with col_btn2:
    if st.button("🔄 Reset"):
        st.session_state.history = []
        st.session_state.active_path = "PATH_PRIMARY"
        st.session_state.primary_cost = 10
        st.session_state.sim.set_scenario(1)
        st.session_state.sim.set_primary_status(True)
        st.session_state.sim.set_primary_cost(10)
        st.session_state.step_counter = 0
        st.rerun()

# Run at least 1 step if history is empty
if not st.session_state.history:
    st.session_state.sim.set_scenario(scenario_id)
    t = st.session_state.sim.generate_telemetry_step()
    st.session_state.history.append(t["primary"])
    st.session_state.step_counter += 1

# Process Latest Telemetry & State
hist_df = pd.DataFrame(st.session_state.history)
feats = st.session_state.fe.extract_features(hist_df)
pred = st.session_state.predictor.predict(feats)
ttf = st.session_state.ttf_pred.estimate_ttf(feats, pred["failure_probability"])

latest_p = st.session_state.history[-1]
p_status = latest_p.get("link_status", "UP")

# Evaluate Candidate Paths
candidates = [
    {
        "path_id": "PATH_PRIMARY",
        "name": "Primary (SW1-SW2)",
        "rtt": latest_p["rtt"],
        "packet_loss": latest_p["packet_loss"],
        "utilization": latest_p["utilization"],
        "risk": pred["failure_probability"],
        "hops": 3,
        "interface": "GigabitEthernet0/1"
    },
    {
        "path_id": "PATH_BACKUP",
        "name": "Backup via SW3",
        "rtt": 18.0,
        "packet_loss": 0.0,
        "utilization": 24.0,
        "risk": 0.05,
        "hops": 4,
        "interface": "GigabitEthernet0/2"
    }
]
path_eval = st.session_state.path_eval.evaluate_paths(candidates, traffic_class=traffic_class)
best_path = path_eval["best_path"]

# Decision Engine Check
decision = st.session_state.decision_engine.evaluate(
    prediction_result=pred,
    ttf_result=ttf,
    primary_link_status=p_status,
    best_candidate_path=best_path,
    current_active_path_id=st.session_state.active_path,
    traffic_class=traffic_class
)

# Execute Reroute if Triggered
if decision["should_reroute"] and st.session_state.active_path == "PATH_PRIMARY":
    st.session_state.active_path = "PATH_BACKUP"
    st.session_state.primary_cost = 100
    st.session_state.cisco.change_metric("SW1", "GigabitEthernet0/1", 100)
    st.session_state.sim.set_primary_cost(100)
    st.session_state.feedback.record_reroute(decision)

# Check Hysteresis if on Backup
hyst = None
if st.session_state.active_path == "PATH_BACKUP":
    hyst = st.session_state.feedback.evaluate_restoration_hysteresis(
        primary_link_up=(p_status == "UP"),
        primary_failure_prob=pred["failure_probability"]
    )
    if hyst["can_restore"]:
        st.session_state.active_path = "PATH_PRIMARY"
        st.session_state.primary_cost = 10
        st.session_state.cisco.restore_metric("SW1", "GigabitEthernet0/1", 10)
        st.session_state.sim.set_primary_cost(10)

# ==============================================================================
# MAIN DASHBOARD INTERFACE
# ==============================================================================
st.title("🛡️ AI-Driven Adaptive Self-Healing Network NOC")
st.caption(f"Real-Time Telemetry Analytics | Machine Learning Link Failure Prediction | Automated OSPF Preemption")

# Section A: Network Topology & Active Path Status
st.subheader("🌐 Section A: Network Topology & Routing State")
col_topo1, col_topo2, col_topo3, col_topo4 = st.columns(4)

with col_topo1:
    st.metric("Active Routing Path", st.session_state.active_path, delta="Preempted" if st.session_state.active_path == "PATH_BACKUP" else "Optimal")
with col_topo2:
    st.metric("Primary OSPF Metric", f"Cost {st.session_state.primary_cost}", delta="+90 Rerouted" if st.session_state.primary_cost > 10 else "Baseline")
with col_topo3:
    st.metric("Primary Physical Status", p_status, delta="Operational" if p_status == "UP" else "Link Down", delta_color="normal" if p_status == "UP" else "inverse")
with col_topo4:
    st.metric("Applied QoS Traffic Class", traffic_class, help="Adjusts penalty weights for latency, loss, and utilization")

# Network Topology Visualizer (ASCII/Card Topology)
with st.expander("🗺️ Interactive Logical Topology Diagram", expanded=True):
    p_color = "status-danger" if p_status == "DOWN" else ("status-warning" if pred["failure_probability"] >= 0.75 else "status-healthy")
    b_color = "status-backup" if st.session_state.active_path == "PATH_BACKUP" else "status-healthy"

    st.markdown(f"""
    ```text
                         [ Router R1 : 10.0.12.1 ]
                                     |
                                     v
                        +-------------------------+
                        | Switch SW1 (Core Ingress)|
                        +-------------------------+
                               /           \\
    (Primary Link: Cost {st.session_state.primary_cost}) /             \\ (Backup Link: Cost 10)
                             /               \\
                            v                 v
            +-------------------------+     +-------------------------+
            | Switch SW2 (Core Egress)| <---| Switch SW3 (Redundant)  |
            +-------------------------+     +-------------------------+
                         |
                         v
              [ Router R2 : 10.0.24.2 ]
    ```
    - **Primary Path Status:** <span class='{p_color}'>SW1 (Gi0/1) <--> SW2 (Gi0/1) | Status: {p_status} | Cost: {st.session_state.primary_cost}</span>
    - **Backup Path Status :** <span class='{b_color}'>SW1 (Gi0/2) <--> SW3 <--> SW2 (Gi0/2) | Status: UP | Effective Cost: 40</span>
    """, unsafe_allow_html=True)

st.divider()

# Section B: AI Prediction Hub
st.subheader("🧠 Section B: AI Failure Risk Prediction & Explainability")
col_ai1, col_ai2, col_ai3, col_ai4 = st.columns(4)

prob_pct = pred["failure_probability"] * 100.0
conf_pct = pred["confidence"] * 100.0

with col_ai1:
    st.metric("Link Health Prediction", pred["predicted_class"], delta=f"Risk: {prob_pct:.1f}%")
with col_ai2:
    st.metric("Model Confidence", f"{conf_pct:.1f}%", help="Confidence gate requires >= 80% to approve preemptive diversion")
with col_ai3:
    st.metric("Estimated Time-to-Failure (TTF)", ttf.get("ttf_range_str", "N/A"), help="Physically extrapolated lead time before collapse")
with col_ai4:
    st.metric("Composite Instability Index", f"{feats['instability_score']:.1f} / 100", help="Weighted multi-factor score: Loss, Jitter slope, CRC growth, Flaps")

# Explainability Indicators
st.markdown("**Explainable Contributing Indicators (Why the AI made this prediction):**")
for ind in pred["contributing_indicators"]:
    st.info(f"🔍 {ind}")

st.divider()

# Section C: Multi-Dimensional Telemetry Stream
st.subheader("📈 Section C: Real-Time Multi-Dimensional Telemetry")
if len(hist_df) > 0:
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("**Round-Trip Latency (RTT) & Jitter Trends (ms)**")
        st.line_chart(hist_df[["rtt", "jitter"]].tail(30))
    with chart_col2:
        st.markdown("**Packet Loss (%) & Cumulative CRC Alignment Errors**")
        st.line_chart(hist_df[["packet_loss", "crc_errors"]].tail(30))

st.divider()

# Section D: Path Evaluation & QoS Engine
st.subheader("🎯 Section D: Candidate Path Evaluation (QoS-Aware)")
st.caption("Objective penalty formula: Lower score = superior candidate path.")

path_rows = []
for p in path_eval["ranked_paths"]:
    is_sel = (p["path_id"] == st.session_state.active_path)
    path_rows.append({
        "Selected": "⭐ ACTIVE" if is_sel else "",
        "Candidate Path": p["name"],
        "Latency RTT (ms)": p["rtt"],
        "Packet Loss (%)": p["packet_loss"],
        "Utilization (%)": f"{p['utilization']}%",
        "Predicted Risk": f"{p['risk']*100:.1f}%",
        "Hop Count": p["hops"],
        "Objective Score": p["score"]
    })
st.table(pd.DataFrame(path_rows))

st.divider()

# Section E: Routing Actions & Hysteresis
st.subheader("⚡ Section E: Routing Controller & Anti-Flapping Hysteresis")
col_act1, col_act2 = st.columns(2)
with col_act1:
    st.markdown("**Latest Routing Controller Decision:**")
    st.markdown(f"""
    - **Action Code:** `{decision['action']}`
    - **Should Reroute:** `{decision['should_reroute']}`
    - **Confidence Gate:** `{'PASSED' if decision['confidence_check_passed'] else 'REJECTED'}`
    - **Rationale:** {decision['reason']}
    """)
with col_act2:
    st.markdown("**Anti-Flapping Route Restoration Hysteresis:**")
    if hyst:
        st.markdown(f"- **Restoration Status:** `{'APPROVED' if hyst['can_restore'] else 'STABILIZING'}`")
        st.markdown(f"- **Stability Elapsed:** `{hyst['elapsed_stability_sec']}s / 15.0s`")
        st.markdown(f"- **Healthy Samples:** `{hyst['healthy_samples']} / 10`")
        st.info(hyst["reason"])
    else:
        st.markdown("Traffic currently on Primary Path. Hysteresis dormant.")

st.divider()

# Section F: Benchmark Comparison: Traditional Reactive OSPF vs AI Proactive
st.subheader("🔬 Section F: Experimental Benchmark Comparison")
st.markdown("Side-by-side comparison of standard reactive OSPF dead-timer convergence vs. AI proactive self-healing.")

bench_path = "results/tables/experiment_comparison.md"
if os.path.exists(bench_path):
    with open(bench_path, "r", encoding="utf-8") as f:
        st.markdown(f.read())
else:
    st.info("Run `python src/experiments/compare_experiments.py` to compile benchmark comparison results.")

# Section G: Event Log
st.subheader("📋 Section G: Event Audit Log")
evt_path = "data/events.csv"
if os.path.exists(evt_path) and os.path.getsize(evt_path) > 50:
    evt_df = pd.read_csv(evt_path)
    st.dataframe(evt_df.tail(15), use_container_width=True)
else:
    st.caption("No events recorded in data/events.csv yet.")
