"""SafeTrack AI - Safety Reports & Compliance Exports View."""
from datetime import datetime
import streamlit as st

from api_client import APIClient, APIError


def render_reports_page(client: APIClient, user: dict) -> None:
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h1 style="color: #0F172A; margin: 0; font-size: 1.8rem;">📑 Safety Reports & Compliance Exports</h1>
            <p style="color: #64748B; margin: 0; font-size: 0.95rem;">
                Generate official petrochemical investigation PDF dossiers and export scoped audit data.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_pdf, tab_csv, tab_summary = st.tabs([
        "📄 Investigation PDF Dossier",
        "📊 Scoped Data Exports (CSV)",
        "📋 Executive HSE Briefing",
    ])

    # =========================================================================
    # TAB 1: PDF Dossier Export
    # =========================================================================
    with tab_pdf:
        st.subheader("Official Investigation PDF Dossier")
        st.caption(
            "Produces a comprehensive, publication-ready PDF dossier containing the incident narrative, "
            "equipment failure context, NLP root-cause evidence, 5-Why analysis, and CAPA sign-offs."
        )

        # Fetch incidents for selection
        try:
            inc_page = client.list_incidents(params={"size": 100})
            incidents_list = inc_page.get("items", [])
        except APIError as e:
            st.error(f"Failed to load incidents: {e.detail}")
            incidents_list = []

        if not incidents_list:
            st.info("No incidents accessible in your current scope.")
        else:
            inc_options = {
                f"{i['reference']} — {i['title']} ({i['status']})": i["id"]
                for i in incidents_list
            }

            sel_label = st.selectbox("Select Incident for PDF Generation", options=list(inc_options.keys()))
            selected_inc_id = inc_options[sel_label]

            # Fetch incident detail for preview
            try:
                inc_detail = client.get_incident(selected_inc_id)
            except APIError as e:
                st.error(f"Failed to fetch detail: {e.detail}")
                inc_detail = None

            if inc_detail:
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 1.2rem; border-radius: 8px; margin: 1rem 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <div>
                                    <span style="font-weight: 700; color: #E65100; font-family: monospace; font-size: 1.1rem;">
                                        {inc_detail['reference']}
                                    </span>
                                    <span style="font-size: 1.1rem; font-weight: 600; color: #0F172A; margin-left: 0.6rem;">
                                        {inc_detail['title']}
                                    </span>
                                </div>
                                <div>
                                    <span style="background-color: #DBEAFE; color: #1E40AF; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                                        {inc_detail['status']}
                                    </span>
                                </div>
                            </div>
                            <div style="color: #475569; font-size: 0.85rem; line-height: 1.5;">
                                📍 <b>Plant:</b> {inc_detail.get('plant_name') or f"Plant #{inc_detail['plant_id']}"} &nbsp;|&nbsp;
                                ⚠️ <b>Severity:</b> {inc_detail['severity']} &nbsp;|&nbsp;
                                🚨 <b>Risk Level:</b> {inc_detail.get('risk_level') or 'Not Evaluated'} &nbsp;|&nbsp;
                                🏥 <b>Injuries:</b> {inc_detail.get('injuries', 0)}
                            </div>
                            <div style="margin-top: 0.8rem; color: #334155; font-size: 0.9rem;">
                                <i>{inc_detail['description'][:220]}...</i>
                            </div>
                            <div style="margin-top: 0.8rem; display: flex; gap: 1rem; color: #64748B; font-size: 0.8rem;">
                                <span>⚙️ Equipment: <b>{len(inc_detail.get('equipment', []))}</b></span>
                                <span>🔍 Root Causes: <b>{len(inc_detail.get('root_causes', []))}</b></span>
                                <span>📎 Attachments: <b>{len(inc_detail.get('attachments', []))}</b></span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                btn_col1, btn_col2 = st.columns([1, 3])
                with btn_col1:
                    try:
                        pdf_data = client.export_incident_pdf(selected_inc_id)
                        filename = f"Investigation_Dossier_{inc_detail['reference']}.pdf"
                        st.download_button(
                            label="📥 Download PDF Dossier",
                            data=pdf_data,
                            file_name=filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                        )
                    except APIError as e:
                        st.error(f"PDF generation error: {e.detail}")

    # =========================================================================
    # TAB 2: Scoped CSV Exports
    # =========================================================================
    with tab_csv:
        col_c1, col_c2 = st.columns(2)

        try:
            plants = client.get_plants()
            plant_id_to_name = {p["id"]: f"{p['name']} ({p['code']})" for p in plants}
        except Exception:
            plant_id_to_name = {}

        # ---------------- Incident CSV Export Card ----------------
        with col_c1:
            with st.container(border=True):
                st.subheader("📋 Incidents Dataset Export")
                st.caption("Raw tabular CSV export of incidents matching applied criteria, respecting plant data scoping.")

                c_plant = st.selectbox(
                    "Plant Filter",
                    options=["All Plants"] + list(plant_id_to_name.keys()),
                    format_func=lambda x: "All Plants" if x == "All Plants" else plant_id_to_name.get(x, f"Plant #{x}"),
                    key="csv_plant_filter",
                )
                c_sev = st.selectbox("Severity Filter", ["All", "Low", "Medium", "High"], key="csv_sev_filter")
                c_risk = st.selectbox("Risk Level", ["All", "LOW", "MEDIUM", "HIGH", "CRITICAL"], key="csv_risk_filter")
                c_stat = st.selectbox(
                    "Workflow Status",
                    ["All", "Reported", "Under Investigation", "Root Cause Identified", "Action Pending", "Verification", "Closed"],
                    key="csv_stat_filter",
                )

                params = {}
                if c_plant != "All Plants":
                    params["plant_id"] = c_plant
                if c_sev != "All":
                    params["severity"] = c_sev
                if c_risk != "All":
                    params["risk_level"] = c_risk
                if c_stat != "All":
                    params["status"] = c_stat

                try:
                    inc_csv = client.export_incidents_csv(params)
                    st.download_button(
                        label="📥 Download Incidents CSV",
                        data=inc_csv,
                        file_name=f"incidents_export_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True,
                    )
                except APIError as e:
                    st.error(f"Export failed: {e.detail}")

        # ---------------- CAPA Actions CSV Export Card ----------------
        with col_c2:
            with st.container(border=True):
                st.subheader("📋 CAPA Actions Dataset Export")
                st.caption("Tabular export of corrective & preventive actions, task owners, target dates, and statuses.")

                act_plant = st.selectbox(
                    "Plant Filter (Actions)",
                    options=["All Plants"] + list(plant_id_to_name.keys()),
                    format_func=lambda x: "All Plants" if x == "All Plants" else plant_id_to_name.get(x, f"Plant #{x}"),
                    key="act_plant_filter",
                )
                act_stat = st.selectbox(
                    "Action Status Filter",
                    ["All", "Proposed", "Approved", "In Progress", "Completed", "Rejected"],
                    key="act_stat_filter",
                )

                act_params = {}
                if act_plant != "All Plants":
                    act_params["plant_id"] = act_plant
                if act_stat != "All":
                    act_params["status"] = act_stat

                try:
                    act_csv = client.export_actions_csv(act_params)
                    st.download_button(
                        label="📥 Download Corrective Actions CSV",
                        data=act_csv,
                        file_name=f"capa_actions_export_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True,
                    )
                except APIError as e:
                    st.error(f"Action export failed: {e.detail}")

    # =========================================================================
    # TAB 3: Executive Briefing
    # =========================================================================
    with tab_summary:
        st.subheader("📋 Petrochemical Executive Safety Briefing")
        st.caption("Dynamic briefing memorandum synthesising current KPIs, watchlists, and CAPA posture.")

        try:
            summary = client.get_dashboard_summary()
            causes = client.get_root_cause_pareto()
            eq_watch = client.get_equipment_watchlist()
        except Exception:
            summary = {}
            causes = []
            eq_watch = []

        now_str = datetime.utcnow().strftime("%B %d, %Y - %H:%M UTC")

        briefing_md = f"""# SafeTrack AI - Petrochemical Executive Safety Memorandum
**Date of Assessment:** {now_str}  
**Prepared For:** Executive Operations & HSE Directorate  
**Scope:** {user.get('role')} Data Visibility Realm

---

### 1. Key Performance Indicators (KPIs)
- **Total Safety Incidents (YTD):** {summary.get('total_incidents', 0)}
- **High / Critical Risk Excursions:** {summary.get('critical_incidents', 0)}
- **Personnel Injuries Logged:** {summary.get('total_injuries', 0)}
- **Open Investigations in Progress:** {summary.get('open_investigations', 0)}
- **Active CAPA Corrective Actions:** {summary.get('open_actions', 0)}
- **Overdue Actions Requiring Escalation:** {summary.get('overdue_actions', 0)}

---

### 2. Root Cause Pareto Breakdown (Leading Contributing Factors)
"""
        if not causes:
            briefing_md += "_No root cause distributions recorded._\n\n"
        else:
            for c in causes[:5]:
                briefing_md += f"- **{c.get('name')}:** {c.get('count')} incidents ({c.get('percentage', 0):.1f}%)\n"

        briefing_md += "\n### 3. Equipment Reliability Watchlist (Repeat Incident Thresholds)\n"
        if not eq_watch:
            briefing_md += "_No equipment currently exceeding failure thresholds._\n\n"
        else:
            for eq in eq_watch[:5]:
                briefing_md += f"- **{eq.get('tag')}** ({eq.get('name')}): {eq.get('incident_count')} incidents | Plant: {eq.get('plant_name')}\n"

        briefing_md += "\n---\n*CONFIDENTIAL — INTERNAL SAFETY COMPLIANCE REPORT*"

        st.markdown(briefing_md)

        st.download_button(
            label="📥 Download Executive Briefing (.md)",
            data=briefing_md.encode("utf-8"),
            file_name=f"HSE_Executive_Briefing_{datetime.utcnow().strftime('%Y%m%d')}.md",
            mime="text/markdown",
        )
