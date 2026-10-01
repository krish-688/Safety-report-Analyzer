"""Executive & Operational HSE Dashboard (Stage 5).

Renders KPI cue cards, monthly incident trends, root cause Pareto chart,
risk distribution donuts, plant comparisons, and the equipment watchlist.
"""
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from api_client import APIClient, APIError

# Petrochemical Hazard & Risk Color Palette
RISK_COLORS = {
    "CRITICAL": "#DC2626",   # Deep Red
    "HIGH": "#EA580C",       # Safety Orange
    "MEDIUM": "#F59E0B",     # Warning Amber
    "LOW": "#10B981",        # Normal Green
    "Unanalyzed": "#94A3B8", # Neutral Gray
}


def render_dashboard_page(client: APIClient, user: dict) -> None:
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
                <h1 style="margin: 0; color: #0F172A; font-size: 2rem;">📊 Executive & Operational HSE Dashboard</h1>
                <span style="color: #64748B;">Petrochemical Safety Incident Trends, Root Causes, and Equipment Risk Intelligence</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    is_global_role = user["role"] in ("Safety Manager", "Management")
    user_plant_id = user.get("plant_id")

    # 1. Filter Bar
    with st.expander("🔎 Dashboard Filters & Scope", expanded=True):
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 1])

        with col_f1:
            if is_global_role:
                try:
                    plants = client.get_plants()
                    plant_options = {"🌐 All Plants (Global Scope)": None}
                    for p in plants:
                        plant_options[f"{p['name']} ({p['code']})"] = p["id"]
                    sel_plant_name = st.selectbox("Plant Facility Scope", list(plant_options.keys()))
                    selected_plant_id = plant_options[sel_plant_name]
                except Exception:
                    selected_plant_id = None
            else:
                selected_plant_id = user_plant_id
                st.selectbox(
                    "Plant Facility Scope",
                    [f"Plant #{user_plant_id} (Fixed to your account)"],
                    disabled=True,
                )

        with col_f2:
            time_horizon = st.selectbox(
                "Time Window",
                ["Last 18 Months (Standard)", "Last 12 Months", "Last 6 Months", "All Time"],
                index=0,
            )

        with col_f3:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            refresh_clicked = st.button("🔄 Refresh Data", use_container_width=True)

    # Calculate date filtering
    now = datetime.utcnow()
    from_date = None
    if time_horizon == "Last 6 Months":
        from_date = (now - timedelta(days=180)).isoformat()
    elif time_horizon == "Last 12 Months":
        from_date = (now - timedelta(days=365)).isoformat()
    elif time_horizon == "Last 18 Months (Standard)":
        from_date = (now - timedelta(days=540)).isoformat()

    filter_params = {}
    if selected_plant_id is not None:
        filter_params["plant_id"] = selected_plant_id
    if from_date:
        filter_params["from_date"] = from_date

    # 2. Fetch Aggregated Metrics
    try:
        summary = client.get_dashboard_summary(params=filter_params)
        trends = client.get_monthly_trends(params=filter_params)
        pareto = client.get_root_cause_pareto(params={"plant_id": selected_plant_id} if selected_plant_id else None)
        watchlist = client.get_equipment_watchlist(params={"plant_id": selected_plant_id} if selected_plant_id else None)
        plant_dist = client.get_plant_distribution() if is_global_role else []
    except APIError as e:
        st.error(f"Failed to load dashboard data: {e.detail}")
        return

    # 3. KPI Cue Cards (Row 1)
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Incidents",
            value=summary["total_incidents"],
            help="Total incidents recorded within the active scope.",
        )
    with col2:
        st.metric(
            label="Critical Risk Events",
            value=summary["critical_risk"],
            delta=f"{summary['critical_risk']} Critical" if summary["critical_risk"] else "None",
            delta_color="inverse",
            help="Incidents classified as Critical Risk (major hazard potential).",
        )
    with col3:
        st.metric(
            label="High Risk Events",
            value=summary["high_risk"],
            help="Incidents classified as High Risk.",
        )
    with col4:
        st.metric(
            label="Open / Investigating",
            value=summary["open_incidents"],
            help="Incidents in Reported, Under Investigation, or Action Pending states.",
        )
    with col5:
        st.metric(
            label="Injuries Recorded",
            value=summary["total_injuries"],
            delta=f"{summary['total_injuries']} injuries" if summary["total_injuries"] else "Zero",
            delta_color="inverse",
            help="Cumulative personnel injuries reported across scoped incidents.",
        )

    st.markdown("---")

    # 4. Chart Row 1: Monthly Trend & Root Cause Pareto
    col_trend, col_pareto = st.columns([1.2, 1])

    with col_trend:
        st.subheader("📈 Monthly Incident Volume & Risk Distribution")
        if not trends:
            st.info("No trend data available for current window.")
        else:
            df_trends = pd.DataFrame(trends)
            fig_trend = go.Figure()

            fig_trend.add_trace(go.Bar(
                x=df_trends["month"], y=df_trends["critical"],
                name="Critical Risk", marker_color=RISK_COLORS["CRITICAL"],
            ))
            fig_trend.add_trace(go.Bar(
                x=df_trends["month"], y=df_trends["high"],
                name="High Risk", marker_color=RISK_COLORS["HIGH"],
            ))
            fig_trend.add_trace(go.Bar(
                x=df_trends["month"], y=df_trends["medium"],
                name="Medium Risk", marker_color=RISK_COLORS["MEDIUM"],
            ))
            fig_trend.add_trace(go.Bar(
                x=df_trends["month"], y=df_trends["low"],
                name="Low Risk", marker_color=RISK_COLORS["LOW"],
            ))

            fig_trend.update_layout(
                barmode="stack",
                xaxis_title="Month",
                yaxis_title="Incident Count",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=30, b=20),
                height=380,
                hovermode="x unified",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    with col_pareto:
        st.subheader("🎯 Root Cause Pareto Analysis (80/20 Rule)")
        if not pareto:
            st.info("No root causes identified yet.")
        else:
            df_pareto = pd.DataFrame(pareto)
            fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])

            fig_pareto.add_trace(
                go.Bar(
                    x=df_pareto["category"],
                    y=df_pareto["count"],
                    name="Frequency",
                    marker_color="#1E3A8A",
                ),
                secondary_y=False,
            )

            fig_pareto.add_trace(
                go.Scatter(
                    x=df_pareto["category"],
                    y=df_pareto["cumulative_percentage"],
                    name="Cumulative %",
                    mode="lines+markers",
                    line=dict(color="#DC2626", width=2.5),
                    marker=dict(size=6),
                ),
                secondary_y=True,
            )

            # 80% Pareto cutoff line
            fig_pareto.add_hline(
                y=80, line_dash="dash", line_color="#EA580C",
                annotation_text="80% Threshold", secondary_y=True,
            )

            fig_pareto.update_layout(
                yaxis=dict(title="Occurrence Count"),
                yaxis2=dict(title="Cumulative %", range=[0, 105], ticksuffix="%"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=30, b=20),
                height=380,
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

    st.markdown("---")

    # 5. Chart Row 2: Risk Donut & Plant Breakdown (or Status Breakdown)
    col_donut, col_dist = st.columns([1, 1.2])

    with col_donut:
        st.subheader("🍩 Risk Level Profile")
        risk_labels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        risk_values = [
            summary["critical_risk"],
            summary["high_risk"],
            summary["medium_risk"],
            summary["low_risk"],
        ]
        if summary.get("unanalyzed_risk"):
            risk_labels.append("Unanalyzed")
            risk_values.append(summary["unanalyzed_risk"])

        fig_donut = go.Figure(data=[go.Pie(
            labels=risk_labels,
            values=risk_values,
            hole=0.45,
            marker=dict(colors=[RISK_COLORS.get(l, "#94A3B8") for l in risk_labels]),
        )])
        fig_donut.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_dist:
        if is_global_role and plant_dist:
            st.subheader("🏭 Incident Distribution by Plant Unit")
            df_plants = pd.DataFrame(plant_dist)
            fig_plant = go.Figure()

            fig_plant.add_trace(go.Bar(
                x=df_plants["plant_name"], y=df_plants["critical"],
                name="Critical Risk", marker_color=RISK_COLORS["CRITICAL"],
            ))
            fig_plant.add_trace(go.Bar(
                x=df_plants["plant_name"], y=df_plants["high"],
                name="High Risk", marker_color=RISK_COLORS["HIGH"],
            ))
            fig_plant.add_trace(go.Bar(
                x=df_plants["plant_name"], y=df_plants["medium"],
                name="Medium Risk", marker_color=RISK_COLORS["MEDIUM"],
            ))
            fig_plant.add_trace(go.Bar(
                x=df_plants["plant_name"], y=df_plants["low"],
                name="Low Risk", marker_color=RISK_COLORS["LOW"],
            ))

            fig_plant.update_layout(
                barmode="stack",
                xaxis_title="Plant Facility",
                yaxis_title="Incidents",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            st.plotly_chart(fig_plant, use_container_width=True)
        else:
            st.subheader("📋 Incident Workflow Status Breakdown")
            wf_labels = ["Reported / Under Inv.", "Root Cause Identified", "Closed"]
            wf_vals = [
                summary["open_incidents"],
                summary["root_causes_identified"],
                summary["closed_incidents"],
            ]
            fig_wf = px.bar(
                x=wf_labels, y=wf_vals,
                labels={"x": "Workflow State", "y": "Incidents"},
                color=wf_labels,
                color_discrete_sequence=["#F59E0B", "#3B82F6", "#10B981"],
            )
            fig_wf.update_layout(
                showlegend=False,
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            st.plotly_chart(fig_wf, use_container_width=True)

    st.markdown("---")

    # 6. Chart Row 3: Equipment Watchlist (Recurring Failures Triggering Thresholds)
    st.subheader("⚠️ High-Frequency Equipment Watchlist (Predictive Maintenance Trigger)")
    st.caption("Equipment units with repeated incidents exceeding the maintenance alert threshold (≥ 3 incidents within 12 months).")

    if not watchlist:
        st.info("No recurring equipment incidents detected within scope.")
    else:
        df_watch = pd.DataFrame(watchlist)

        # Highlight table
        table_rows = []
        for w in watchlist:
            flag = "🚨 THRESHOLD EXCEEDED" if w["threshold_exceeded"] else "Normal"
            table_rows.append({
                "Equipment Tag": w["tag"],
                "Equipment Name": w["name"],
                "Equipment Type": w["equipment_type"],
                "Plant Facility": w["plant_name"],
                "Incident Count": w["incident_count"],
                "Alert Status": flag,
            })

        st.dataframe(table_rows, use_container_width=True, hide_index=True)
