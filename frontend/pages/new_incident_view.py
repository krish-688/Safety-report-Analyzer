"""Report New Incident view with equipment linking and plant validation."""
from datetime import datetime
import streamlit as st

from api_client import APIClient, APIError


def render_new_incident_page(client: APIClient, user: dict) -> None:
    st.title("➕ Report Safety Incident")
    st.caption("Record a newly observed safety incident, loss of containment, or operational event.")

    is_safety_manager = user["role"] == "Safety Manager"
    prefill = st.session_state.get("prefill_incident", {})

    # 1. Fetch plants for selector
    try:
        plants = client.get_plants()
        plant_options = {f"{p['name']} ({p['code']})": p["id"] for p in plants}
    except Exception:
        plant_options = {}

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        if is_safety_manager:
            plant_name = st.selectbox(
                "Plant Unit *",
                list(plant_options.keys()),
                key="new_inc_plant_sel",
            )
            active_plant_id = plant_options.get(plant_name)
        else:
            active_plant_id = user.get("plant_id")
            st.text_input(
                "Assigned Plant",
                value=f"Plant #{active_plant_id} (Fixed to your account)",
                disabled=True,
            )

    # 2. Fetch Equipment for active plant
    equipment_choices: dict[str, int] = {}
    if active_plant_id:
        try:
            eq_list = client.get_plant_equipment(active_plant_id)
            for eq in eq_list:
                label = f"{eq['tag']} — {eq['name']} ({eq['equipment_type']})"
                equipment_choices[label] = eq["id"]
        except Exception:
            equipment_choices = {}

    with col_meta2:
        selected_equipment_labels = st.multiselect(
            "Linked Equipment Units",
            options=list(equipment_choices.keys()),
            help="Select one or more equipment units involved in this incident.",
        )
        selected_equipment_ids = [equipment_choices[lbl] for lbl in selected_equipment_labels]

    with st.form("new_incident_form"):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input(
                "Incident Title *",
                value=prefill.get("title", ""),
                placeholder="e.g. Mechanical seal leak on pump P-101A",
            )
            incident_type = st.selectbox(
                "Incident Type *",
                [
                    "Equipment Failure",
                    "Loss of Containment",
                    "Process Upset",
                    "Permit Violation",
                    "Near Miss",
                    "Instrument Failure",
                    "Procedure Deviation",
                    "Weather / Environmental",
                ],
                index=0,
            )
            severity = st.selectbox("Observed Severity *", ["Low", "Medium", "High"], index=1)
            injuries = st.number_input(
                "Number of Personnel Injured",
                min_value=0,
                max_value=50,
                value=prefill.get("injuries", 0),
            )

        with col2:
            occurred_date = st.date_input("Date of Occurrence *", value=datetime.today())
            occurred_time = st.time_input("Time of Occurrence *", value=datetime.now().time())

        description = st.text_area(
            "Incident Description * (Provide detailed narrative for NLP analysis)",
            value=prefill.get("text", ""),
            placeholder="Describe what occurred, equipment involved, abnormal readings, operating state, and personnel actions...",
            height=130,
        )

        col3, col4 = st.columns(2)
        with col3:
            immediate_actions = st.text_area(
                "Immediate Actions Taken",
                placeholder="e.g. Equipment isolated, fire watch posted, line depressurised...",
                height=80,
            )
        with col4:
            damage_details = st.text_area(
                "Observed Equipment / Environmental Damage",
                placeholder="e.g. Bearing casing cracked, 50 liters wash water spilled to sump...",
                height=80,
            )

        submitted = st.form_submit_button("Submit Incident Report", type="primary", use_container_width=True)

        if submitted:
            if not title or len(title.strip()) < 3:
                st.error("Please provide a valid incident title (minimum 3 characters).")
                return
            if not description or len(description.strip()) < 10:
                st.error("Please provide a comprehensive description (minimum 10 characters).")
                return
            if not active_plant_id:
                st.error("Plant assignment is required.")
                return

            occurred_dt = datetime.combine(occurred_date, occurred_time).isoformat()
            payload = {
                "title": title.strip(),
                "occurred_at": occurred_dt,
                "plant_id": active_plant_id,
                "incident_type": incident_type,
                "description": description.strip(),
                "severity": severity,
                "injuries": int(injuries),
                "damage_details": damage_details.strip() if damage_details else None,
                "immediate_actions": immediate_actions.strip() if immediate_actions else None,
                "equipment_ids": selected_equipment_ids,
            }

            try:
                created = client.create_incident(payload)
                st.success(f"✅ Incident recorded successfully with reference **{created['reference']}**!")
                st.session_state.prefill_incident = {}
                st.balloons()
                st.info("You can inspect the new incident, run AI Root Cause Analysis, or upload attachments in the **Incident Explorer**.")
            except APIError as e:
                st.error(f"Failed to create incident: {e.detail}")
