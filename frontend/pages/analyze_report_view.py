"""Analyze Report View: AI text analysis playground and incident pre-check."""
import streamlit as st

from api_client import APIClient, APIError

RISK_BADGES = {
    "CRITICAL": "🔴 CRITICAL RISK",
    "HIGH": "🟠 HIGH RISK",
    "MEDIUM": "🟡 MEDIUM RISK",
    "LOW": "🟢 LOW RISK",
}


def render_analyze_report_page(client: APIClient, user: dict) -> None:
    st.title("🧠 AI Safety Incident & Root Cause Analyzer")
    st.caption("Test the NLP analysis pipeline on draft reports, operator narratives, or shift logs to predict risk levels and root causes.")

    col_input, col_meta = st.columns([2.5, 1])

    with col_meta:
        st.subheader("Report Parameters")
        sample_choice = st.selectbox(
            "Load Sample Scenario",
            [
                "-- Custom Input --",
                "Compressor Seal Failure (Equipment)",
                "Permit Violation & Welding (Human)",
                "Exchanger Thermal Runaway (Process)",
                "Severe Rainstorm & Flooding (Environmental)",
            ],
        )

        title_input = st.text_input("Incident Title (Optional)", placeholder="e.g. Hydrocarbon release at heat exchanger")
        incident_type = st.selectbox(
            "Incident Type",
            [
                "Loss of Containment",
                "Equipment Failure",
                "Process Upset",
                "Permit Violation",
                "Near Miss",
                "Procedure Deviation",
            ],
        )
        severity = st.selectbox("Observed Severity", ["Low", "Medium", "High"], index=1)
        injuries = st.number_input("Injuries Reported", min_value=0, max_value=20, value=0)

    # Sample texts for testing
    default_text = ""
    if sample_choice == "Compressor Seal Failure (Equipment)":
        default_text = (
            "During routine monitoring of compressor K-101, vibration levels exceeded alert thresholds. "
            "The primary mechanical seal failed, leading to a flammable hydrocarbon release in the compressor house. "
            "Preventive maintenance had been postponed due to parts delays. The operator tripped the machine and isolated the suction valve."
        )
    elif sample_choice == "Permit Violation & Welding (Human)":
        default_text = (
            "A contractor began hot work grinding near storage tank T-201 without obtaining a valid hot work permit or gas clearance. "
            "The shift handover log did not record pending maintenance. The supervisor halted the work immediately upon field audit. Operator fatigue was noted."
        )
    elif sample_choice == "Exchanger Thermal Runaway (Process)":
        default_text = (
            "Temperature in reactor R-101 climbed beyond the safe operating envelope following a sudden cooling water flow reduction. "
            "The temperature control loop responded sluggishly. Management of change procedure was bypassed during the recent setpoint adjustment."
        )
    elif sample_choice == "Severe Rainstorm & Flooding (Environmental)":
        default_text = (
            "Torrential monsoon rain and lightning caused stormwater sump overflow and electrical tripping of auxiliary cooling pump P-302. "
            "Extreme weather and surface flooding hindered initial operator access."
        )

    with col_input:
        st.subheader("Incident Narrative / Report Text")
        report_text = st.text_area(
            "Paste report text here for NLP extraction and classification:",
            value=default_text,
            height=200,
            placeholder="Type or paste the narrative description of the safety event...",
        )
        run_btn = st.button("🚀 Analyze Safety Narrative", type="primary", use_container_width=True)

    if run_btn:
        if not report_text or len(report_text.strip()) < 5:
            st.error("Please provide at least 5 characters of narrative text to analyze.")
            return

        with st.spinner("Processing natural language extraction & root cause classification..."):
            try:
                res = client.analyze_text({
                    "title": title_input,
                    "text": report_text.strip(),
                    "incident_type": incident_type,
                    "severity": severity,
                    "injuries": int(injuries),
                })
            except APIError as e:
                st.error(f"Analysis failed: {e.detail}")
                return

        st.markdown("---")
        st.subheader("📋 AI Analysis Findings")

        risk_level = res["risk_level"]
        risk_conf = res["risk_confidence"]
        analysis_data = res["result"]

        # Risk Banner
        badge_text = RISK_BADGES.get(risk_level, f"RISK: {risk_level}")
        col_res1, col_res2, col_res3 = st.columns([1.5, 1.5, 1])

        with col_res1:
            st.markdown(f"### {badge_text}")
            st.metric("Risk Confidence", f"{risk_conf * 100:.1f}%")

        with col_res2:
            cues = analysis_data.get("risk", {}).get("cues", [])
            st.markdown("**Hazard Cues Detected:**")
            if cues:
                for c in cues:
                    st.markdown(f"- ⚠️ `{c}`")
            else:
                st.caption("No acute hazard cues detected.")

        with col_res3:
            kws = analysis_data.get("keywords", [])
            st.markdown("**Keywords Extracted:**")
            st.write(", ".join([f"`{k}`" for k in kws[:6]]))

        st.markdown("---")
        st.subheader("🔍 Predicted Root Causes & Evidence")

        root_causes = analysis_data.get("root_causes", [])
        if not root_causes:
            st.info("No specific root cause category identified above threshold.")
        else:
            for rc in root_causes:
                with st.container(border=True):
                    col_cat, col_conf = st.columns([3, 1])
                    with col_cat:
                        st.markdown(f"#### 🏷️ {rc['category']}")
                        st.markdown(f"**Identified Evidence:**\n> \"*{rc.get('evidence', '')}*\"")
                    with col_conf:
                        st.metric("Category Match", f"{rc['confidence'] * 100:.0f}%")

        # Action Button to Create Incident
        if user["role"] in ("Safety Officer", "Safety Manager"):
            st.markdown("---")
            if st.button("📝 Create Formal Incident from this Report", type="primary"):
                st.session_state.prefill_incident = {
                    "title": title_input or "Analyzed Safety Incident",
                    "text": report_text,
                    "injuries": int(injuries),
                }
                st.session_state.active_page = "new_incident"
                st.rerun()
