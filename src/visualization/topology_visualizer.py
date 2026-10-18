"""
Network Operations Center (NOC) Interactive Topology Visualizer.
Renders an interactive, responsive SVG/HTML network topology map with real-time
directional traffic flow, dynamic OSPF cost badges, link status coloring,
and AI health indicators for Cisco self-healing networks.
"""

from typing import Dict, Any, Optional

def render_topology_svg(
    active_path: str = "R1 → SW1 → SW2 → R2",
    primary_status: str = "UP",
    backup_status: str = "UP",
    primary_cost: int = 10,
    backup_cost: int = 10,
    primary_telemetry: Optional[Dict[str, Any]] = None,
    backup_telemetry: Optional[Dict[str, Any]] = None,
    ai_prediction: Optional[Dict[str, Any]] = None,
    decision: Optional[Dict[str, Any]] = None,
    height: int = 420
) -> str:
    """
    Generates a dark-navy NOC interactive SVG/HTML diagram.
    Nodes: R1, SW1, SW2, SW3, R2.
    Primary Path: R1 -> SW1 -> SW2 -> R2.
    Backup Path:  R1 -> SW1 -> SW3 -> SW2 -> R2.
    """
    p_tel = primary_telemetry or {}
    b_tel = backup_telemetry or {}
    pred = ai_prediction or {}
    dec = decision or {}

    p_rtt = float(p_tel.get("rtt", 12.0))
    p_loss = float(p_tel.get("packet_loss", 0.0))
    p_crc = int(p_tel.get("crc_errors", 0))
    p_util = float(p_tel.get("utilization", 35.0))

    b_rtt = float(b_tel.get("rtt", 18.0))
    b_loss = float(b_tel.get("packet_loss", 0.0))
    b_crc = int(b_tel.get("crc_errors", 0))
    b_util = float(b_tel.get("utilization", 25.0))

    risk = float(pred.get("failure_probability", 0.0))
    pred_class = pred.get("predicted_class", "HEALTHY")

    is_backup_active = ("SW3" in active_path)
    is_primary_active = not is_backup_active

    # Link condition evaluation
    # SW1 -> SW2 (Primary Link)
    if primary_status == "DOWN":
        sw1_sw2_state = "FAILED"
        sw1_sw2_color = "#ef4444"
        sw1_sw2_dash = "8,4"
    elif risk >= 0.75 or p_loss > 3.0:
        sw1_sw2_state = "CONGESTED"
        sw1_sw2_color = "#ef4444"
        sw1_sw2_dash = "6,4"
    elif risk >= 0.40 or p_loss > 0.5 or p_crc > 5:
        sw1_sw2_state = "WARNING"
        sw1_sw2_color = "#f59e0b"
        sw1_sw2_dash = "none"
    elif is_primary_active:
        sw1_sw2_state = "ACTIVE"
        sw1_sw2_color = "#10b981"
        sw1_sw2_dash = "none"
    else:
        sw1_sw2_state = "STANDBY"
        sw1_sw2_color = "#3b82f6"
        sw1_sw2_dash = "none"

    # SW1 -> SW3 and SW3 -> SW2 (Backup Transit Links)
    if backup_status == "DOWN":
        backup_state = "FAILED"
        backup_color = "#ef4444"
        backup_dash = "8,4"
    elif b_loss > 4.0 or b_util > 80.0:
        backup_state = "CONGESTED"
        backup_color = "#ef4444"
        backup_dash = "6,4"
    elif b_loss > 0.5 or b_rtt > 40.0:
        backup_state = "WARNING"
        backup_color = "#f59e0b"
        backup_dash = "none"
    elif is_backup_active:
        backup_state = "ACTIVE"
        backup_color = "#10b981"
        backup_dash = "none"
    else:
        backup_state = "STANDBY"
        backup_color = "#3b82f6"
        backup_dash = "4,4"

    # R1 -> SW1 (Ingress link)
    r1_sw1_color = "#10b981"
    # SW2 -> R2 (Egress link)
    sw2_r2_color = "#10b981"

    # Active flow particle animations
    primary_flow_anim = ""
    backup_flow_anim = ""

    if is_primary_active and primary_status == "UP":
        primary_flow_anim = """
        <line x1="280" y1="130" x2="160" y2="230" stroke="#34d399" stroke-width="3" stroke-dasharray="10,14" opacity="0.9">
            <animate attributeName="stroke-dashoffset" from="48" to="0" dur="1s" repeatCount="indefinite" />
        </line>
        """

    if is_backup_active and backup_status == "UP":
        backup_flow_anim = """
        <line x1="320" y1="130" x2="440" y2="230" stroke="#34d399" stroke-width="3" stroke-dasharray="10,14" opacity="0.9">
            <animate attributeName="stroke-dashoffset" from="48" to="0" dur="1.2s" repeatCount="indefinite" />
        </line>
        <line x1="420" y1="240" x2="180" y2="240" stroke="#34d399" stroke-width="3" stroke-dasharray="10,14" opacity="0.9">
            <animate attributeName="stroke-dashoffset" from="48" to="0" dur="1s" repeatCount="indefinite" />
        </line>
        """

    # Primary badge text
    p_badge_text = f"Cost {primary_cost} | {sw1_sw2_state}"
    b_badge_text = f"Cost 40 Total | {backup_state}"

    # Path breadcrumb text
    path_pill_color = "#10b981" if is_primary_active and sw1_sw2_state != "CONGESTED" else ("#3b82f6" if is_backup_active else "#f59e0b")
    route_status_title = "ACTIVE PATH: PRIMARY ROUTE (SW1 ➔ SW2)" if is_primary_active else "PREEMPTIVE PATH: REDUNDANT TRANSIT (SW1 ➔ SW3 ➔ SW2)"

    html_code = f"""
    <div style="background-color: #0b111e; border: 1px solid #1e293b; border-radius: 12px; padding: 16px; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; color: #f8fafc; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
        <!-- Header Banner -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: {path_pill_color}; box-shadow: 0 0 10px {path_pill_color};"></span>
                <span style="font-weight: 700; font-size: 0.95rem; letter-spacing: 0.5px; color: #e2e8f0;">{route_status_title}</span>
            </div>
            <div style="display: flex; gap: 8px; font-size: 0.75rem;">
                <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3);">● Active Flow</span>
                <span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(59, 130, 246, 0.3);">● Standby Link</span>
                <span style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.3);">▲ Warning</span>
                <span style="background: rgba(239, 68, 68, 0.15); color: #f87171; padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(239, 68, 68, 0.3);">✕ Degraded/Down</span>
            </div>
        </div>

        <!-- Interactive SVG Canvas -->
        <svg viewBox="0 0 600 370" style="width: 100%; height: auto; max-height: 380px; display: block; overflow: visible;">
            <defs>
                <!-- Arrowhead markers -->
                <marker id="arrow-green" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981" />
                </marker>
                <marker id="arrow-blue" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#3b82f6" />
                </marker>
                <marker id="arrow-amber" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b" />
                </marker>
                <marker id="arrow-red" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444" />
                </marker>

                <!-- Glow filters -->
                <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#10b981" flood-opacity="0.6"/>
                </filter>
                <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#ef4444" flood-opacity="0.8"/>
                </filter>
                <filter id="glow-blue" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="2" flood-color="#3b82f6" flood-opacity="0.5"/>
                </filter>

                <!-- Grid pattern -->
                <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                    <circle cx="2" cy="2" r="1" fill="#1e293b" opacity="0.6" />
                </pattern>
            </defs>

            <!-- Grid Background -->
            <rect width="600" height="370" fill="url(#grid)" />

            <!-- ===================== LINKS ===================== -->
            <!-- Link: R1 -> SW1 -->
            <line x1="300" y1="45" x2="300" y2="105" stroke="{r1_sw1_color}" stroke-width="3" />
            <line x1="300" y1="45" x2="300" y2="105" stroke="#34d399" stroke-width="2" stroke-dasharray="6,8">
                <animate attributeName="stroke-dashoffset" from="28" to="0" dur="0.8s" repeatCount="indefinite" />
            </line>
            <text x="310" y="78" fill="#94a3b8" font-size="10" font-family="monospace">Cost 10</text>

            <!-- Link: SW1 -> SW2 (Primary Link: Gi0/1) -->
            <line x1="270" y1="125" x2="160" y2="215" stroke="{sw1_sw2_color}" stroke-width="3.5" stroke-dasharray="{sw1_sw2_dash}" {"filter='url(#glow-green)'" if is_primary_active and sw1_sw2_state == "ACTIVE" else ("filter='url(#glow-red)'" if sw1_sw2_state in ("FAILED", "CONGESTED") else "")} />
            {primary_flow_anim}

            <!-- Link: SW1 -> SW3 (Backup Link Part 1: Gi0/2) -->
            <line x1="330" y1="125" x2="440" y2="215" stroke="{backup_color}" stroke-width="3" stroke-dasharray="{backup_dash}" {"filter='url(#glow-green)'" if is_backup_active else ""} />

            <!-- Link: SW3 -> SW2 (Backup Link Part 2: SW3:Gi0/1 -> SW2:Gi0/2) -->
            <line x1="410" y1="230" x2="190" y2="230" stroke="{backup_color}" stroke-width="3" stroke-dasharray="{backup_dash}" {"filter='url(#glow-green)'" if is_backup_active else ""} />
            {backup_flow_anim}

            <!-- Link: SW2 -> R2 (Egress link) -->
            <line x1="150" y1="250" x2="150" y2="310" stroke="{sw2_r2_color}" stroke-width="3" />
            <line x1="150" y1="250" x2="150" y2="310" stroke="#34d399" stroke-width="2" stroke-dasharray="6,8">
                <animate attributeName="stroke-dashoffset" from="28" to="0" dur="0.8s" repeatCount="indefinite" />
            </line>
            <text x="160" y="285" fill="#94a3b8" font-size="10" font-family="monospace">Cost 10</text>

            <!-- ===================== LINK BADGES / LABELS ===================== -->
            <!-- Primary Link Badge (SW1:Gi0/1 -> SW2) -->
            <g transform="translate(145, 145)">
                <rect width="110" height="24" rx="4" fill="#0f172a" stroke="{sw1_sw2_color}" stroke-width="1.2" />
                <text x="55" y="16" fill="{sw1_sw2_color}" font-size="10" font-weight="700" text-anchor="middle" font-family="monospace">{p_badge_text}</text>
            </g>
            <text x="215" y="140" fill="#64748b" font-size="9" font-family="monospace">Gi0/1</text>

            <!-- Backup Link Badge (SW1:Gi0/2 -> SW3) -->
            <g transform="translate(345, 145)">
                <rect width="110" height="24" rx="4" fill="#0f172a" stroke="{backup_color}" stroke-width="1.2" />
                <text x="55" y="16" fill="{backup_color}" font-size="10" font-weight="700" text-anchor="middle" font-family="monospace">{b_badge_text}</text>
            </g>
            <text x="365" y="140" fill="#64748b" font-size="9" font-family="monospace">Gi0/2</text>

            <!-- SW3 -> SW2 Transit Label -->
            <text x="300" y="222" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">SW3:Gi0/1 ➔ SW2:Gi0/2 (Cost 10)</text>

            <!-- ===================== NODES ===================== -->
            <!-- Node: R1 (Source Gateway) -->
            <g transform="translate(300, 35)">
                <circle r="22" fill="#0f172a" stroke="#3b82f6" stroke-width="2.5" />
                <text x="0" y="4" fill="#ffffff" font-size="11" font-weight="800" text-anchor="middle" font-family="monospace">R1</text>
                <text x="0" y="-28" fill="#94a3b8" font-size="10" font-weight="600" text-anchor="middle">Source Gateway</text>
                <text x="0" y="-17" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">10.0.12.1</text>
            </g>

            <!-- Node: SW1 (Distribution Ingress Switch) -->
            <g transform="translate(300, 115)">
                <rect x="-42" y="-18" width="84" height="36" rx="6" fill="#0f172a" stroke="{'#10b981' if is_primary_active and primary_status == 'UP' else '#3b82f6'}" stroke-width="2.2" />
                <text x="0" y="4" fill="#ffffff" font-size="12" font-weight="800" text-anchor="middle" font-family="monospace">SW1</text>
                <text x="52" y="-2" fill="#94a3b8" font-size="10" font-weight="600">Distribution Core (Ingress)</text>
                <text x="52" y="10" fill="#64748b" font-size="9" font-family="monospace">10.0.12.2 [AI Control]</text>
            </g>

            <!-- Node: SW2 (Distribution Egress Switch) -->
            <g transform="translate(150, 230)">
                <rect x="-42" y="-18" width="84" height="36" rx="6" fill="#0f172a" stroke="{'#10b981' if primary_status == 'UP' else '#ef4444'}" stroke-width="2.2" />
                <text x="0" y="4" fill="#ffffff" font-size="12" font-weight="800" text-anchor="middle" font-family="monospace">SW2</text>
                <text x="-50" y="-5" fill="#94a3b8" font-size="10" font-weight="600" text-anchor="end">Core Egress</text>
                <text x="-50" y="8" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">10.0.24.1</text>
            </g>

            <!-- Node: SW3 (Redundant Backup Transit Switch) -->
            <g transform="translate(450, 230)">
                <rect x="-42" y="-18" width="84" height="36" rx="6" fill="#0f172a" stroke="{'#10b981' if is_backup_active else '#3b82f6'}" stroke-width="2.2" />
                <text x="0" y="4" fill="#ffffff" font-size="12" font-weight="800" text-anchor="middle" font-family="monospace">SW3</text>
                <text x="50" y="-5" fill="#94a3b8" font-size="10" font-weight="600">Backup Transit</text>
                <text x="50" y="8" fill="#64748b" font-size="9" font-family="monospace">10.0.13.2</text>
            </g>

            <!-- Node: R2 (Destination Gateway) -->
            <g transform="translate(150, 325)">
                <circle r="22" fill="#0f172a" stroke="#3b82f6" stroke-width="2.5" />
                <text x="0" y="4" fill="#ffffff" font-size="11" font-weight="800" text-anchor="middle" font-family="monospace">R2</text>
                <text x="32" y="0" fill="#94a3b8" font-size="10" font-weight="600">Destination Gateway</text>
                <text x="32" y="12" fill="#64748b" font-size="9" font-family="monospace">10.0.24.2</text>
            </g>
        </svg>

        <!-- Live Telemetry & Path Summary Footer -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; border-top: 1px solid #1e293b; padding-top: 10px; font-size: 0.8rem;">
            <div style="background: #0f172a; padding: 8px 12px; border-radius: 6px; border-left: 3px solid {sw1_sw2_color};">
                <span style="color: #94a3b8; font-size: 0.72rem; display: block;">PRIMARY LINK (SW1:Gi0/1)</span>
                <span style="font-weight: 700; color: #f8fafc;">RTT: {p_rtt:.1f}ms | Loss: {p_loss:.1f}%</span>
                <span style="color: #64748b; font-size: 0.7rem; display: block;">Errors: {p_crc} CRC | Util: {p_util:.0f}%</span>
            </div>
            <div style="background: #0f172a; padding: 8px 12px; border-radius: 6px; border-left: 3px solid {backup_color};">
                <span style="color: #94a3b8; font-size: 0.72rem; display: block;">BACKUP TRANSIT (via SW3)</span>
                <span style="font-weight: 700; color: #f8fafc;">RTT: {b_rtt:.1f}ms | Loss: {b_loss:.1f}%</span>
                <span style="color: #64748b; font-size: 0.7rem; display: block;">Errors: {b_crc} CRC | Util: {b_util:.0f}%</span>
            </div>
            <div style="background: #0f172a; padding: 8px 12px; border-radius: 6px; border-left: 3px solid {'#10b981' if risk < 0.4 else ('#f59e0b' if risk < 0.75 else '#ef4444')};">
                <span style="color: #94a3b8; font-size: 0.72rem; display: block;">AI FAILURE RISK / STATE</span>
                <span style="font-weight: 700; color: #f8fafc;">{pred_class} ({risk*100:.1f}%)</span>
                <span style="color: #64748b; font-size: 0.7rem; display: block;">Confidence: {pred.get('confidence', 1.0)*100:.0f}%</span>
            </div>
            <div style="background: #0f172a; padding: 8px 12px; border-radius: 6px; border-left: 3px solid {path_pill_color};">
                <span style="color: #94a3b8; font-size: 0.72rem; display: block;">DECISION / REROUTE STATUS</span>
                <span style="font-weight: 700; color: #f8fafc;">{dec.get('action', 'NO_ACTION')}</span>
                <span style="color: #64748b; font-size: 0.7rem; display: block;">Cost: P={primary_cost} | B={backup_cost}</span>
            </div>
        </div>
    </div>
    """
    return html_code
