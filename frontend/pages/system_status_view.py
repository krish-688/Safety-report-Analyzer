"""System Status, Diagnostics & Compliance Audit Trail View."""
from datetime import datetime
import streamlit as st

from api_client import APIClient, APIError


def render_system_status_page(client: APIClient, user: dict) -> None:
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h1 style="color: #0F172A; margin: 0; font-size: 1.8rem;">⚙️ Platform Diagnostics & Audit Compliance</h1>
            <p style="color: #64748B; margin: 0; font-size: 0.95rem;">
                Inspect API connectivity, service health, and enterprise security audit logs.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_diag, tab_audit = st.tabs(["🖥️ System Diagnostics", "📜 Enterprise Audit Trail"])

    # ------------------ TAB 1: Diagnostics ------------------
    with tab_diag:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Service Health & Topology")
            try:
                health = client.get_health()
                st.success(f"Backend Status: **{health.get('status', 'OK').upper()}**")
                st.markdown(f"- **Application Name:** `{health.get('app')}`")
                st.markdown(f"- **API Base URL:** `{client.base_url}`")
                st.markdown(f"- **FastAPI OpenAPI Docs:** [Interactive Swagger UI]({client.base_url.replace('/api/v1', '')}/docs)")
            except APIError as e:
                st.error(f"Backend unreachable: {e.detail}")

        with col2:
            st.subheader("Platform Architecture")
            st.markdown(
                """
                - **Backend Engine:** FastAPI, SQLAlchemy 2.0, Pydantic v2
                - **Frontend Layer:** Streamlit Thin Client, Plotly Visualization Engine
                - **Database Compatibility:** SQLite (dev) / PostgreSQL & MySQL production-ready
                - **Authentication & Security:** Argon2 / Bcrypt password hashing, JWT Bearer tokens (30m expiry, 5-failure 15m lockout)
                - **Role-Based Access Control (RBAC):** Strict plant-level data scoping, opaque 404 filtering
                """
            )

        st.markdown("---")
        st.subheader("Operational Plant Facilities")
        try:
            plants = client.list_all_plants()
            st.dataframe(plants, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to load plants: {e}")

    # ------------------ TAB 2: Audit Trail ------------------
    with tab_audit:
        st.subheader("Enterprise Security & Change Audit Log")
        st.caption("Immutable record of authentication attempts, incident workflows, CAPA decisions, and admin changes.")

        f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
        with f_col1:
            action_search = st.text_input("Filter by Action", placeholder="e.g. user, incident, equipment, seed")
        with f_col2:
            entity_filter = st.selectbox(
                "Entity Type",
                options=["All Entities", "user", "incident", "investigation", "action", "equipment", "plant_unit", "system"],
            )
        with f_col3:
            limit = st.selectbox("Record Limit", options=[25, 50, 100, 200], index=1)

        ent_arg = None if entity_filter == "All Entities" else entity_filter
        try:
            logs = client.list_audit_logs(
                action=action_search or None,
                entity_type=ent_arg,
                limit=limit,
            )
        except APIError as e:
            st.error(f"Failed to fetch audit logs: {e.detail}")
            logs = []

        st.markdown(f"**Loaded {len(logs)} audit entries**")

        if not logs:
            st.info("No audit logs found matching criteria.")
        else:
            table_data = []
            for entry in logs:
                created_raw = entry.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                    dt_fmt = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    dt_fmt = created_raw

                table_data.append({
                    "Timestamp": dt_fmt,
                    "Action": entry.get("action"),
                    "Entity": f"{entry.get('entity_type')} #{entry.get('entity_id') or '-'}",
                    "User ID": entry.get("user_id") or "System",
                    "Details": str(entry.get("details") or {}),
                })

            st.dataframe(table_data, use_container_width=True)
