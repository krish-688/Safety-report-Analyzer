"""Investigations and Corrective Actions (CAPA) view."""
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

from api_client import APIClient, APIError

ACTION_STATUS_BADGES = {
    "Proposed": "🟡 Proposed (Awaiting Approval)",
    "Approved": "🔵 Approved",
    "In Progress": "🟣 In Progress",
    "Completed": "🟢 Completed",
    "Rejected": "🔴 Rejected",
}


def render_investigations_page(client: APIClient, user: dict) -> None:
    st.title("🔍 Investigations & CAPA Workflow")
    st.caption("Manage root cause investigations, assign CAPA actions, and execute Plant Manager approval workflows.")

    tab_inv, tab_capa = st.tabs(["🔎 Incident Investigation", "📋 CAPA Actions Tracker"])

    with tab_inv:
        _render_investigation_tab(client, user)

    with tab_capa:
        _render_capa_tracker_tab(client, user)


def _render_investigation_tab(client: APIClient, user: dict) -> None:
    can_write = user["role"] in ("Safety Officer", "Safety Manager")
    is_safety_manager = user["role"] == "Safety Manager"

    # Fetch incidents for selection
    try:
        inc_data = client.get_incidents(params={"size": 100})
        incidents = inc_data.get("items", [])
    except APIError as e:
        st.error(f"Failed to load incidents: {e.detail}")
        incidents = []

    if not incidents:
        st.info("No incidents found in current scope.")
        return

    sel_label = st.selectbox(
        "Select Incident to Investigate",
        options=[f"{i['id']}: {i['reference']} — {i['title']}" for i in incidents],
    )
    inc_id = int(sel_label.split(":")[0])

    try:
        detail = client.get_incident(inc_id)
        inv = client.get_investigation(inc_id)
    except APIError as e:
        st.error(f"Failed to fetch incident details: {e.detail}")
        return

    # Stepper & Header
    st.markdown(f"### Incident: `{detail['reference']}` — {detail['title']}")
    st.markdown(f"**Current Status:** `{detail['status']}` · **Severity:** `{detail['severity']}` · **Plant:** {detail.get('plant_name') or detail['plant_id']}")

    # Investigation Card
    if not inv:
        st.warning("⚠️ No investigation record initiated for this incident yet.")
        if can_write:
            st.markdown("Initiate the investigation to assign an investigator, due date, and log initial findings:")
            with st.form("start_inv_form"):
                due_d = st.date_input("Investigation Due Date", value=date.today() + timedelta(days=14))
                initial_findings = st.text_area("Initial Findings / 5-Why Observations", placeholder="Enter preliminary findings...")
                evidence_notes = st.text_area("Collected Physical & Operational Evidence", placeholder="Log physical samples, DCS trend logs, or interview records...")
                sub_btn = st.form_submit_button("🚀 Start Investigation", type="primary")

                if sub_btn:
                    try:
                        client.create_investigation(
                            inc_id,
                            {
                                "due_date": due_d.isoformat(),
                                "findings": initial_findings.strip() if initial_findings else None,
                                "evidence": evidence_notes.strip() if evidence_notes else None,
                            },
                        )
                        st.success("Investigation initiated! Status updated to 'Under Investigation'.")
                        st.rerun()
                    except APIError as e:
                        st.error(f"Failed to start investigation: {e.detail}")
    else:
        with st.container(border=True):
            col_i1, col_i2, col_i3 = st.columns(3)
            with col_i1:
                st.markdown(f"**Lead Investigator:** {inv.get('investigator_name') or 'User #' + str(inv.get('investigator_id'))}")
            with col_i2:
                st.markdown(f"**Due Date:** {inv.get('due_date') or 'No date set'}")
            with col_i3:
                verified_str = f"✅ Verified by {inv.get('verified_by_name') or 'Safety Manager'}" if inv.get("verified_by_id") else "⏳ Verification Pending"
                st.markdown(f"**Verification:** {verified_str}")

            st.markdown(f"**Findings & 5-Why Analysis:**\n> {inv.get('findings') or 'No findings logged yet.'}")
            if inv.get("evidence"):
                st.markdown(f"**Evidence & Logs:**\n> {inv['evidence']}")

            if can_write and detail["status"] != "Closed":
                with st.expander("✏️ Update Investigation Findings"):
                    with st.form(f"upd_inv_{inv['id']}"):
                        upd_due = st.date_input("Update Due Date", value=datetime.strptime(inv["due_date"], "%Y-%m-%d").date() if inv.get("due_date") else date.today() + timedelta(days=7))
                        upd_findings = st.text_area("Findings", value=inv.get("findings") or "", height=100)
                        upd_evidence = st.text_area("Evidence", value=inv.get("evidence") or "", height=80)
                        if st.form_submit_button("Save Findings", type="primary"):
                            try:
                                client.update_investigation(
                                    inc_id,
                                    {
                                        "due_date": upd_due.isoformat(),
                                        "findings": upd_findings.strip(),
                                        "evidence": upd_evidence.strip(),
                                    },
                                )
                                st.success("Investigation findings updated!")
                                st.rerun()
                            except APIError as e:
                                st.error(f"Update failed: {e.detail}")

        # Verification & Close (Safety Manager only)
        if is_safety_manager and detail["status"] != "Closed":
            st.markdown("#### Formal Verification & Incident Closure")
            st.caption("Safety Managers review verified root causes and ensure corrective actions are underway before closing.")
            if st.button("🏁 Verify & Close Incident", type="primary", key=f"close_btn_{inc_id}"):
                try:
                    client.close_investigation(inc_id)
                    st.success(f"Incident {detail['reference']} formally closed!")
                    st.balloons()
                    st.rerun()
                except APIError as e:
                    st.error(f"Closure failed: {e.detail}")


def _render_capa_tracker_tab(client: APIClient, user: dict) -> None:
    st.subheader("📋 Corrective & Preventive Action Plan (CAPA)")

    can_approve = user["role"] in ("Plant Manager", "Safety Manager")
    can_create = user["role"] in ("Safety Officer", "Safety Manager")

    # Status filter
    sel_status = st.selectbox(
        "Filter by Action Status",
        ["All", "Proposed", "Approved", "In Progress", "Completed", "Rejected"],
    )
    status_filter = None if sel_status == "All" else sel_status

    try:
        actions = client.list_actions(params={"status": status_filter})
    except APIError as e:
        st.error(f"Failed to fetch actions: {e.detail}")
        actions = []

    # Create new action popover
    if can_create:
        with st.popover("➕ Propose New Corrective Action"):
            _render_new_action_dialog(client, user)

    st.markdown(f"**Total Actions:** {len(actions)}")

    if not actions:
        st.info("No corrective actions match the selected filter.")
        return

    for act in actions:
        with st.container(border=True):
            col_a1, col_a2 = st.columns([3, 1.5])

            with col_a1:
                badge = ACTION_STATUS_BADGES.get(act["status"], act["status"])
                st.markdown(f"#### {act['action_type']} Action: {act['description']}")
                st.caption(f"Incident: `{act.get('incident_reference') or '#' + str(act['incident_id'])}` · Plant: **{act.get('plant_name') or 'Plant'}** · Due: **{act['due_date']}**")
                if act.get("equipment_tag"):
                    st.markdown(f"Equipment: 🏷️ `{act['equipment_tag']}`")
                st.markdown(f"Status: **{badge}**")

            with col_a2:
                act_id = act["id"]
                # 1. Approval workflow (Plant Manager or Safety Manager)
                if can_approve and act["status"] == "Proposed":
                    st.markdown("**Plant Manager Approval Required:**")
                    col_appr, col_rej = st.columns(2)
                    with col_appr:
                        if st.button("✅ Approve", key=f"appr_act_{act_id}", type="primary", use_container_width=True):
                            try:
                                client.approve_action(act_id, approved=True)
                                st.success("Action approved!")
                                st.rerun()
                            except APIError as e:
                                st.error(e.detail)
                    with col_rej:
                        if st.button("❌ Reject", key=f"rej_act_{act_id}", use_container_width=True):
                            try:
                                client.approve_action(act_id, approved=False)
                                st.warning("Action rejected.")
                                st.rerun()
                            except APIError as e:
                                st.error(e.detail)

                # 2. Execution progress (In Progress / Completed)
                if act["status"] == "Approved":
                    if st.button("▶️ Start Implementation", key=f"start_act_{act_id}", use_container_width=True):
                        try:
                            client.update_action(act_id, {"status": "In Progress"})
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)

                elif act["status"] == "In Progress":
                    if st.button("✅ Mark Completed", key=f"comp_act_{act_id}", type="primary", use_container_width=True):
                        try:
                            client.update_action(act_id, {"status": "Completed"})
                            st.success("Action marked completed!")
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)


def _render_new_action_dialog(client: APIClient, user: dict) -> None:
    st.markdown("##### Propose New CAPA Action Item")

    # Select incident
    try:
        inc_data = client.get_incidents(params={"size": 100})
        inc_items = inc_data.get("items", [])
    except Exception:
        inc_items = []

    if not inc_items:
        st.warning("No incidents available to associate.")
        return

    sel_inc = st.selectbox(
        "Associated Incident *",
        options=[f"{i['id']}: {i['reference']} — {i['title']}" for i in inc_items],
    )
    target_inc_id = int(sel_inc.split(":")[0])

    action_type = st.selectbox("Action Classification *", ["Corrective", "Preventive", "Maintenance"])
    action_desc = st.text_area("Action Description *", placeholder="Specify mechanical repair, operating procedure update, or engineering redesign...")
    due_date = st.date_input("Target Due Date *", value=date.today() + timedelta(days=30))

    if st.button("Submit Action for Approval", type="primary"):
        if not action_desc or len(action_desc.strip()) < 5:
            st.error("Please enter a comprehensive action description (minimum 5 characters).")
            return

        try:
            client.create_action(
                target_inc_id,
                {
                    "action_type": action_type,
                    "description": action_desc.strip(),
                    "due_date": due_date.isoformat(),
                },
            )
            st.success("Corrective action proposed! Awaiting Plant Manager review.")
            st.rerun()
        except APIError as e:
            st.error(f"Failed to propose action: {e.detail}")
