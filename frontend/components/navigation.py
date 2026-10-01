"""Role-based Navigation Component for SafeTrack AI."""
import streamlit as st

from api_client import APIClient

ROLE_PAGES = {
    "Admin": [
        ("👥 User Management", "admin_users"),
        ("🏭 Plants & Equipment", "admin_plants_equipment"),
        ("🔔 Alert Thresholds", "alerts"),
        ("📜 Audit & System Health", "system_status"),
    ],
    "Safety Manager": [
        ("📊 Dashboard", "dashboard"),
        ("📋 Incident Explorer", "incidents"),
        ("➕ Report Incident", "new_incident"),
        ("🧠 Analyze Report", "analyze_report"),
        ("🔍 Investigations & CAPA", "investigations"),
        ("🔔 Alerts & Thresholds", "alerts"),
        ("📑 Reports & Exports", "reports"),
    ],
    "Plant Manager": [
        ("📊 Dashboard", "dashboard"),
        ("📋 Incident Explorer", "incidents"),
        ("🔍 Investigations & CAPA", "investigations"),
        ("🔔 Alerts & Thresholds", "alerts"),
        ("📑 Reports & Exports", "reports"),
    ],
    "Safety Officer": [
        ("📊 Dashboard", "dashboard"),
        ("📋 Incident Explorer", "incidents"),
        ("➕ Report Incident", "new_incident"),
        ("🧠 Analyze Report", "analyze_report"),
        ("🔍 Investigations & CAPA", "investigations"),
        ("🔔 Alerts & Notifications", "alerts"),
        ("📑 Reports & Exports", "reports"),
    ],
    "Management": [
        ("📊 Executive Dashboard", "dashboard"),
        ("📋 Incident Explorer", "incidents"),
        ("🧠 Analyze Report", "analyze_report"),
        ("📑 Safety Reports", "reports"),
    ],
}



def render_sidebar(client: APIClient, user: dict) -> str:
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 0.5rem 0 1rem 0;">
                <h2 style="color: #E65100; margin: 0; font-size: 1.5rem;">🛡️ SafeTrack AI</h2>
                <span style="color: #64748B; font-size: 0.85rem;">Petrochemical HSE Intelligence</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        role = user.get("role", "Safety Officer")
        plant_id = user.get("plant_id")

        st.markdown(
            f"""
            <div style="background-color: #F1F5F9; padding: 0.8rem; border-radius: 8px; margin-bottom: 1.2rem; border-left: 4px solid #E65100;">
                <div style="font-weight: 600; color: #0F172A; font-size: 0.95rem;">{user.get('name', 'User')}</div>
                <div style="color: #475569; font-size: 0.8rem;">{user.get('email', '')}</div>
                <div style="margin-top: 0.4rem; display: flex; gap: 0.4rem; flex-wrap: wrap;">
                    <span style="background-color: #E2E8F0; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">{role}</span>
                    {f'<span style="background-color: #FEF3C7; color: #92400E; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Plant #{plant_id}</span>' if plant_id else '<span style="background-color: #DBEAFE; color: #1E40AF; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">All Plants</span>'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        unread_count = 0
        try:
            unread_count = client.get_unread_alerts_count()
        except Exception:
            unread_count = 0

        pages = ROLE_PAGES.get(role, ROLE_PAGES["Safety Officer"])
        formatted_pages = []
        for lbl, key in pages:
            if key == "alerts" and unread_count > 0:
                formatted_pages.append((f"{lbl} ({unread_count})", key))
            else:
                formatted_pages.append((lbl, key))

        labels = [p[0] for p in formatted_pages]
        page_keys = {p[0]: p[1] for p in formatted_pages}

        # Retrieve or initialize active page
        current_page_key = st.session_state.get("active_page", pages[0][1])
        default_index = 0
        for idx, (lbl, key) in enumerate(formatted_pages):
            if key == current_page_key:
                default_index = idx
                break

        selected_label = st.radio(
            "Navigation",
            options=labels,
            index=default_index,
            label_visibility="collapsed",
        )
        active_page = page_keys[selected_label]
        st.session_state.active_page = active_page

        st.markdown("---")

        if st.button("🚪 Sign Out", use_container_width=True):
            try:
                client.logout()
            except Exception:
                pass
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.active_page = None
            st.rerun()

        st.caption("SafeTrack AI v0.3.0 · Stage 4")
        return active_page
