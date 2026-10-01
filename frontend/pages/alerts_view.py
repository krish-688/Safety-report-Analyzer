"""SafeTrack AI - Alerts & Notification Center.

Provides automated HSE event notifications, repeat equipment failure warnings,
overdue investigation/action tracking, and threshold configuration.
"""
from datetime import datetime
import streamlit as st

from api_client import APIClient, APIError


ALERT_TYPE_METADATA = {
    "critical_incident": {
        "label": "🚨 CRITICAL INCIDENT",
        "bg_color": "#FEE2E2",
        "border_color": "#DC2626",
        "text_color": "#991B1B",
        "icon": "🚨",
    },
    "high_risk_incident": {
        "label": "⚠️ HIGH RISK",
        "bg_color": "#FFEDD5",
        "border_color": "#EA580C",
        "text_color": "#9A3412",
        "icon": "⚠️",
    },
    "equipment_threshold": {
        "label": "⚙️ EQUIPMENT REPEAT WARNING",
        "bg_color": "#FEF3C7",
        "border_color": "#D97706",
        "text_color": "#92400E",
        "icon": "⚙️",
    },
    "investigation_overdue": {
        "label": "⏰ INVESTIGATION OVERDUE",
        "bg_color": "#EDE9FE",
        "border_color": "#7C3AED",
        "text_color": "#5B21B6",
        "icon": "⏰",
    },
    "action_overdue": {
        "label": "📋 ACTION OVERDUE",
        "bg_color": "#FCE7F3",
        "border_color": "#DB2777",
        "text_color": "#9D174D",
        "icon": "📋",
    },
    "recurring_cause": {
        "label": "🔄 RECURRING ROOT CAUSE",
        "bg_color": "#E0E7FF",
        "border_color": "#4F46E5",
        "text_color": "#3730A3",
        "icon": "🔄",
    },
}


def _render_alert_card(client: APIClient, alert: dict):
    alert_type = str(alert.get("alert_type", "")).lower().replace(" ", "_")
    meta = ALERT_TYPE_METADATA.get(
        alert_type,
        {
            "label": alert_type.upper().replace("_", " "),
            "bg_color": "#F1F5F9",
            "border_color": "#94A3B8",
            "text_color": "#334155",
            "icon": "🔔",
        },
    )

    is_read = alert.get("is_read", False)
    border_left = f"6px solid {meta['border_color']}"
    opacity = "0.75" if is_read else "1.0"
    created_str = alert.get("created_at", "")
    try:
        dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        time_formatted = dt.strftime("%b %d, %Y - %H:%M")
    except Exception:
        time_formatted = created_str

    ref = alert.get("incident_reference")
    eq = alert.get("equipment_tag")

    st.markdown(
        f"""
        <div style="background-color: {meta['bg_color']}; border-left: {border_left};
                    padding: 0.9rem 1.2rem; border-radius: 8px; margin-bottom: 0.8rem;
                    opacity: {opacity}; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <span style="font-weight: 700; color: {meta['text_color']}; font-size: 0.8rem; letter-spacing: 0.5px;">
                        {meta['label']}
                    </span>
                    {f'<span style="background-color: #FFFFFF; color: #1E293B; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; border: 1px solid #CBD5E1;">Ref: {ref}</span>' if ref else ''}
                    {f'<span style="background-color: #FFFFFF; color: #1E293B; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; border: 1px solid #CBD5E1;">Eq: {eq}</span>' if eq else ''}
                </div>
                <div style="color: #64748B; font-size: 0.75rem;">
                    {time_formatted} {' · <span style="color: #10B981; font-weight: 600;">✓ Read</span>' if is_read else ' · <span style="color: #DC2626; font-weight: 600;">● Unread</span>'}
                </div>
            </div>
            <div style="font-weight: 600; font-size: 1rem; color: #0F172A; margin-bottom: 0.3rem;">
                {alert.get('title', '')}
            </div>
            <div style="color: #334155; font-size: 0.9rem; line-height: 1.4;">
                {alert.get('message', '')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 6])
    with col1:
        if not is_read:
            if st.button("Mark as Read", key=f"read_{alert['id']}", use_container_width=True):
                try:
                    client.mark_alert_read(alert["id"])
                    st.toast("Alert marked as read.", icon="✅")
                    st.rerun()
                except APIError as e:
                    st.error(f"Failed to update alert: {e.detail}")
    with col2:
        if alert.get("incident_id"):
            if st.button("Open Incident", key=f"jump_{alert['id']}", use_container_width=True):
                st.session_state.selected_incident_id = alert["incident_id"]
                st.session_state.active_page = "incidents"
                st.rerun()


def render_alerts_page(client: APIClient, user: dict):
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
                <h1 style="margin: 0; color: #0F172A; font-size: 1.8rem;">🔔 Safety Alerts & Notification Center</h1>
                <p style="margin: 0; color: #64748B; font-size: 0.95rem;">Real-time threshold triggers, overdue investigation monitoring, and high-risk notifications</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    role = user.get("role", "")
    can_tune_thresholds = role in ("Admin", "Safety Manager", "Plant Manager")

    tabs = ["📢 Live Alert Feed"]
    if can_tune_thresholds:
        tabs.append("⚙️ Threshold Configuration")

    selected_tabs = st.tabs(tabs)

    # ------------------ TAB 1: Alert Feed ------------------
    with selected_tabs[0]:
        # Top KPI Metrics & Actions Bar
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns([2, 2, 2, 3])

        try:
            unread_count = client.get_unread_alerts_count()
        except Exception:
            unread_count = 0

        with kpi_col1:
            st.metric("Unread Alerts", unread_count)

        with kpi_col4:
            st.write("")
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🔄 Scan Overdue", help="Scan for overdue investigations and corrective actions", use_container_width=True):
                    with st.spinner("Scanning for overdue items..."):
                        try:
                            res = client.scan_alerts()
                            count = res.get("new_alerts_created", 0)
                            st.toast(f"Scan complete: {count} new alert(s) generated.", icon="🔍")
                            st.rerun()
                        except APIError as e:
                            st.error(f"Scan failed: {e.detail}")
            with btn_col2:
                if st.button("✅ Read All", help="Mark all current alerts as read", use_container_width=True):
                    try:
                        res = client.mark_all_alerts_read()
                        st.toast(res.get("message", "All marked as read."), icon="✅")
                        st.rerun()
                    except APIError as e:
                        st.error(f"Failed: {e.detail}")

        st.markdown("---")

        # Filters
        f_col1, f_col2, f_col3 = st.columns([2, 3, 2])
        with f_col1:
            unread_only = st.checkbox("Show Unread Only", value=(unread_count > 0))
        with f_col2:
            alert_type_filter = st.selectbox(
                "Filter by Alert Type",
                options=["All Types"] + list(ALERT_TYPE_METADATA.keys()),
                format_func=lambda x: "All Types" if x == "All Types" else ALERT_TYPE_METADATA[x]["label"],
            )
        with f_col3:
            limit = st.slider("Max Alerts to Load", min_value=10, max_value=100, value=30, step=10)

        # Load alerts
        try:
            alerts = client.list_alerts(unread_only=unread_only, limit=limit)
        except APIError as e:
            st.error(f"Failed to load alerts: {e.detail}")
            return

        if alert_type_filter != "All Types":
            alerts = [a for a in alerts if str(a.get("alert_type", "")).lower().replace(" ", "_") == alert_type_filter]

        with kpi_col2:
            critical_high_count = sum(
                1 for a in alerts if str(a.get("alert_type", "")).lower().replace(" ", "_") in ("critical_incident", "high_risk_incident")
            )
            st.metric("Critical / High Alerts", critical_high_count)

        with kpi_col3:
            st.metric("Showing Alerts", len(alerts))

        if not alerts:
            st.info(
                "🎉 No alerts match your current filter. All safety threshold criteria are healthy!",
                icon="ℹ️",
            )
        else:
            for alert in alerts:
                _render_alert_card(client, alert)

    # ------------------ TAB 2: Threshold Tuning ------------------
    if can_tune_thresholds and len(selected_tabs) > 1:
        with selected_tabs[1]:
            st.subheader("🛡️ Safety Automation & Escalation Thresholds")
            st.markdown(
                """
                Configure active system rules that automatically notify plant leadership,
                flag overdue safety investigations, and issue maintenance alarms.
                """
            )

            try:
                thresholds = client.list_thresholds()
            except APIError as e:
                st.error(f"Failed to load thresholds: {e.detail}")
                return

            if not thresholds:
                st.warning("No thresholds defined in the system.")
                return

            for th in thresholds:
                t_key = th.get("key")
                t_val = th.get("value", 0)
                t_desc = th.get("description", "")

                with st.container():
                    st.markdown(
                        f"""
                        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 1rem 1.2rem;
                                    border-radius: 8px; margin-bottom: 1rem;">
                            <div style="font-weight: 700; color: #0F172A; font-size: 1rem; font-family: monospace;">
                                {t_key}
                            </div>
                            <div style="color: #64748B; font-size: 0.85rem; margin-top: 0.2rem;">
                                {t_desc}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    t_col1, t_col2, t_col3 = st.columns([2, 1, 4])
                    with t_col1:
                        new_val = st.number_input(
                            f"Value for `{t_key}`",
                            value=int(t_val),
                            min_value=0,
                            max_value=365,
                            step=1,
                            key=f"thresh_input_{t_key}",
                            disabled=(role not in ("Admin", "Safety Manager")),
                        )
                    with t_col2:
                        st.write("")
                        st.write("")
                        if role in ("Admin", "Safety Manager"):
                            if st.button("Update", key=f"save_{t_key}", use_container_width=True):
                                try:
                                    client.update_threshold(t_key, new_val)
                                    st.toast(f"Threshold '{t_key}' updated to {new_val}.", icon="💾")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Failed to update threshold: {e.detail}")
