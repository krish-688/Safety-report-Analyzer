"""Incident Explorer view: list, filters, CSV export, inspection, edits, and NLP reviews."""
import streamlit as st

from api_client import APIClient, APIError

WORKFLOW_STEPS = [
    "Reported",
    "Under Investigation",
    "Root Cause Identified",
    "Action Pending",
    "Verification",
    "Closed",
]


def render_incidents_page(client: APIClient, user: dict) -> None:
    st.title("📋 Incident Explorer")
    st.caption("Review, filter, investigate, edit, and analyze recorded safety incidents.")

    can_write = user["role"] in ("Safety Officer", "Safety Manager")
    is_global_role = user["role"] in ("Safety Manager", "Management")

    # 1. Filter Controls
    with st.expander("🔍 Search & Filter Incidents", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            search_query = st.text_input("Search Text", placeholder="Reference, title, description...").strip()

        with col2:
            severity_options = ["All", "Low", "Medium", "High"]
            sel_severity = st.selectbox("Severity", severity_options)

        with col3:
            risk_options = ["All", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
            sel_risk = st.selectbox("Risk Level", risk_options)

        with col4:
            status_options = ["All"] + WORKFLOW_STEPS
            sel_status = st.selectbox("Workflow Status", status_options)

        col5, col6 = st.columns(2)
        with col5:
            incident_type_filter = st.selectbox(
                "Incident Type",
                ["All", "Equipment Failure", "Loss of Containment", "Process Upset", "Permit Violation", "Near Miss", "Instrument Failure", "Procedure Deviation"],
            )
        with col6:
            if is_global_role:
                try:
                    plants = client.get_plants()
                    plant_opts = {"All Plants": None}
                    for p in plants:
                        plant_opts[f"{p['name']} ({p['code']})"] = p["id"]
                    sel_pname = st.selectbox("Plant Filter", list(plant_opts.keys()))
                    filter_plant_id = plant_opts[sel_pname]
                except Exception:
                    filter_plant_id = None
            else:
                filter_plant_id = user.get("plant_id")
                st.text_input("Plant Filter", value=f"Plant #{filter_plant_id} (Fixed to your account)", disabled=True)

    # 2. Pagination State
    if "incident_page" not in st.session_state:
        st.session_state.incident_page = 1

    page_size = 20
    params: dict = {
        "page": st.session_state.incident_page,
        "size": page_size,
    }
    if search_query:
        params["search"] = search_query
    if sel_severity != "All":
        params["severity"] = sel_severity
    if sel_risk != "All":
        params["risk_level"] = sel_risk
    if sel_status != "All":
        params["status"] = sel_status
    if incident_type_filter != "All":
        params["incident_type"] = incident_type_filter
    if filter_plant_id:
        params["plant_id"] = filter_plant_id

    # 3. Fetch Data & CSV Export Row
    try:
        data = client.get_incidents(params=params)
        items = data.get("items", [])
        total = data.get("total", 0)
    except APIError as e:
        st.error(f"Failed to fetch incidents: {e.detail}")
        items, total = [], 0

    col_count, col_export = st.columns([3, 1])

    with col_count:
        total_pages = max(1, (total + page_size - 1) // page_size)
        st.markdown(f"**Total Incidents:** {total} · **Page {st.session_state.incident_page} of {total_pages}**")

    with col_export:
        if st.button("📥 Export Filtered CSV", use_container_width=True):
            try:
                csv_bytes = client.export_csv(params=params)
                st.download_button(
                    label="💾 Download incidents.csv",
                    data=csv_bytes,
                    file_name="incidents_export.csv",
                    mime="text/csv",
                    key="download_csv_btn",
                )
            except APIError as e:
                st.error(f"CSV export failed: {e.detail}")

    if not items:
        st.info("No safety incidents match the selected filters.")
        return

    # 4. Render Table
    table_rows = [
        {
            "ID": item["id"],
            "Reference": item["reference"],
            "Title": item["title"],
            "Plant": item.get("plant_name") or f"Plant #{item['plant_id']}",
            "Occurred At": item["occurred_at"][:16].replace("T", " "),
            "Severity": item["severity"],
            "Risk": item.get("risk_level") or "—",
            "Status": item["status"],
            "Injuries": item.get("injuries", 0),
        }
        for item in items
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # Pagination buttons
    col_p1, col_p2, col_p3 = st.columns([1, 4, 1])
    with col_p1:
        if st.session_state.incident_page > 1:
            if st.button("◀ Previous Page"):
                st.session_state.incident_page -= 1
                st.rerun()
    with col_p3:
        if st.session_state.incident_page < total_pages:
            if st.button("Next Page ▶"):
                st.session_state.incident_page += 1
                st.rerun()

    # 5. Incident Detail Inspector
    st.markdown("---")
    st.subheader("🔎 Inspect & Manage Incident Details")

    selected_ref = st.selectbox(
        "Select Incident to Inspect",
        options=[f"{i['id']}: {i['reference']} — {i['title']}" for i in items],
    )

    if selected_ref:
        inc_id = int(selected_ref.split(":")[0])
        _render_incident_detail(client, user, inc_id)


def _render_workflow_stepper(current_status: str) -> None:
    """Render a visual stepper indicating the workflow progress."""
    cols = st.columns(len(WORKFLOW_STEPS))
    reached = True
    for idx, step in enumerate(WORKFLOW_STEPS):
        with cols[idx]:
            if step == current_status:
                st.markdown(f"**🔵 {step}**")
                reached = False
            elif reached:
                st.markdown(f"✅ {step}")
            else:
                st.markdown(f"⚪ <span style='color: #94A3B8;'>{step}</span>", unsafe_allow_html=True)


def _render_incident_detail(client: APIClient, user: dict, incident_id: int) -> None:
    try:
        detail = client.get_incident(incident_id)
    except APIError as e:
        st.error(f"Failed to load details: {e.detail}")
        return

    can_write = user["role"] in ("Safety Officer", "Safety Manager")
    is_author_or_manager = (user["role"] == "Safety Manager") or (user.get("plant_id") == detail["plant_id"])

    # Workflow stepper
    _render_workflow_stepper(detail["status"])
    st.markdown("<br>", unsafe_allow_html=True)

    col_meta1, col_meta2, col_meta3 = st.columns(3)
    with col_meta1:
        st.markdown(f"**Reference:** `{detail['reference']}`")
        st.markdown(f"**Plant:** {detail.get('plant_name') or detail['plant_id']}")
        st.markdown(f"**Reported By:** {detail.get('created_by_name') or 'User #' + str(detail['created_by_id'])}")

    with col_meta2:
        st.markdown(f"**Occurred At:** {detail['occurred_at'][:16].replace('T', ' ')}")
        st.markdown(f"**Severity:** `{detail['severity']}`")
        st.markdown(f"**Injuries:** {detail['injuries']}")

    with col_meta3:
        risk = detail.get("risk_level") or "Unanalyzed"
        conf = detail.get("risk_confidence")
        conf_str = f" ({conf * 100:.0f}%)" if conf else ""
        st.markdown(f"**Risk Level:** `{risk}`{conf_str}")
        st.markdown(f"**Workflow Status:** `{detail['status']}`")

    st.markdown(f"**Description:**\n> {detail['description']}")

    if detail.get("immediate_actions"):
        st.markdown(f"**Immediate Actions:** {detail['immediate_actions']}")
    if detail.get("damage_details"):
        st.markdown(f"**Damage Details:** {detail['damage_details']}")

    # Equipment List
    equipment = detail.get("equipment", [])
    if equipment:
        eq_tags = [f"🏷️ `{e['tag']}` ({e['name']})" for e in equipment]
        st.markdown(f"**Linked Equipment:** {', '.join(eq_tags)}")

    # Action Toolbar: Edit & Delete
    if can_write and is_author_or_manager:
        col_act1, col_act2, _ = st.columns([1, 1, 3])
        with col_act1:
            with st.popover("✏️ Edit Incident"):
                _render_edit_dialog(client, user, detail)
        with col_act2:
            # Delete button (Safety Manager, or Safety Officer in Reported state)
            can_delete = (user["role"] == "Safety Manager") or (detail["status"] == "Reported")
            if can_delete:
                with st.popover("🗑️ Delete"):
                    st.warning(f"Delete incident {detail['reference']} permanently?")
                    if st.button("Confirm Delete", key=f"confirm_del_{detail['id']}", type="primary"):
                        try:
                            client.delete_incident(detail["id"])
                            st.success("Incident deleted successfully.")
                            st.rerun()
                        except APIError as e:
                            st.error(f"Delete failed: {e.detail}")

    # Tabs: Root Causes, Attachments
    tab_nlp, tab_att = st.tabs(["🧠 AI Root Cause Analysis & Review", "📎 Attachments"])

    with tab_nlp:
        _render_nlp_section(client, user, detail)

    with tab_att:
        _render_attachments_section(client, user, detail)


def _render_edit_dialog(client: APIClient, user: dict, detail: dict) -> None:
    st.markdown("#### Update Incident Information")
    with st.form(f"edit_form_{detail['id']}"):
        new_title = st.text_input("Title", value=detail["title"])
        new_desc = st.text_area("Description", value=detail["description"], height=100)
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            new_actions = st.text_area("Immediate Actions", value=detail.get("immediate_actions") or "")
        with col_e2:
            new_damage = st.text_area("Damage Details", value=detail.get("damage_details") or "")

        save_btn = st.form_submit_button("Save Changes", type="primary")
        if save_btn:
            try:
                client.update_incident(
                    detail["id"],
                    {
                        "title": new_title,
                        "description": new_desc,
                        "immediate_actions": new_actions or None,
                        "damage_details": new_damage or None,
                    },
                )
                st.success("Incident updated successfully!")
                st.rerun()
            except APIError as e:
                st.error(f"Update failed: {e.detail}")


def _render_nlp_section(client: APIClient, user: dict, detail: dict) -> None:
    inc_id = detail["id"]
    can_edit = user["role"] in ("Safety Officer", "Safety Manager")

    col_btn1, col_btn2 = st.columns([1.5, 2.5])
    with col_btn1:
        if can_edit:
            if st.button("🚀 Run NLP Analysis", key=f"run_nlp_{inc_id}", type="primary"):
                try:
                    res = client.analyze_incident(inc_id)
                    st.success("AI Analysis generated successfully!")
                    st.rerun()
                except APIError as e:
                    st.error(f"NLP Analysis failed: {e.detail}")

    with col_btn2:
        if can_edit:
            with st.popover("➕ Add Manual Root Cause"):
                _render_manual_cause_dialog(client, inc_id)

    root_causes = detail.get("root_causes", [])
    if not root_causes:
        st.info("No root causes analyzed or identified yet. Click 'Run NLP Analysis' above.")
    else:
        st.markdown("#### Identified & Suggested Root Causes")
        for rc in root_causes:
            with st.container(border=True):
                col_rc1, col_rc2 = st.columns([3, 1])
                with col_rc1:
                    st.markdown(f"**Category:** {rc.get('root_cause_name') or rc['root_cause_id']} `[{rc['source']}]`")
                    if rc.get("confidence"):
                        st.caption(f"Confidence: {rc['confidence'] * 100:.1f}%")
                    if rc.get("evidence"):
                        st.markdown(f"*Evidence snippet:* \"{rc['evidence']}\"")
                with col_rc2:
                    st.markdown(f"Status: **`{rc['review_status']}`**")
                    if can_edit and rc["review_status"] == "Suggested":
                        if st.button("✅ Accept", key=f"accept_rc_{rc['id']}"):
                            client.review_root_cause(inc_id, action="accept", incident_root_cause_id=rc["id"])
                            st.rerun()
                        if st.button("❌ Reject", key=f"reject_rc_{rc['id']}"):
                            client.review_root_cause(inc_id, action="reject", incident_root_cause_id=rc["id"])
                            st.rerun()


def _render_manual_cause_dialog(client: APIClient, incident_id: int) -> None:
    st.markdown("##### Add Verified Root Cause")
    # Categories
    cause_options = {
        "Human Factors": 1,
        "Equipment": 2,
        "Process": 3,
        "Environmental": 4,
        "Accidental/Unplanned": 5,
    }
    sel_cat = st.selectbox("Category", list(cause_options.keys()))
    evidence_text = st.text_area("Findings / Evidence", placeholder="Describe observed root cause factors...")

    if st.button("Save Root Cause", key=f"save_manual_rc_{incident_id}", type="primary"):
        if not evidence_text or len(evidence_text.strip()) < 3:
            st.error("Please enter supporting evidence or findings.")
            return
        try:
            client.review_root_cause(
                incident_id,
                action="add",
                root_cause_id=cause_options[sel_cat],
                evidence=evidence_text.strip(),
            )
            st.success("Root cause added!")
            st.rerun()
        except APIError as e:
            st.error(f"Failed to add root cause: {e.detail}")


def _render_attachments_section(client: APIClient, user: dict, detail: dict) -> None:
    inc_id = detail["id"]
    can_upload = user["role"] in ("Safety Officer", "Safety Manager")

    if can_upload:
        uploaded_file = st.file_uploader(
            "Upload Document or Image",
            type=["pdf", "docx", "png", "jpg", "csv", "txt"],
            key=f"file_uploader_{inc_id}",
        )
        if uploaded_file is not None:
            if st.button("Upload File", key=f"upload_btn_{inc_id}"):
                try:
                    client.upload_attachment(
                        inc_id,
                        file_bytes=uploaded_file.getvalue(),
                        filename=uploaded_file.name,
                        content_type=uploaded_file.type,
                    )
                    st.success(f"Uploaded {uploaded_file.name} successfully!")
                    st.rerun()
                except APIError as e:
                    st.error(f"Upload failed: {e.detail}")

    attachments = detail.get("attachments", [])
    if not attachments:
        st.caption("No attachments uploaded for this incident.")
    else:
        for att in attachments:
            with st.container(border=True):
                col_a1, col_a2, col_a3 = st.columns([3, 1, 1])
                with col_a1:
                    size_kb = att["size_bytes"] / 1024
                    st.markdown(f"📄 **{att['filename']}** ({size_kb:.1f} KB)")
                    st.caption(f"Uploaded by: {att.get('uploaded_by_name') or 'User'} · {att['uploaded_at'][:16].replace('T', ' ')}")
                with col_a2:
                    if st.button("📥 Download", key=f"dl_att_{att['id']}"):
                        try:
                            content = client.download_attachment(inc_id, att["id"])
                            st.download_button(
                                label="Save File",
                                data=content,
                                file_name=att["filename"],
                                mime=att.get("content_type") or "application/octet-stream",
                                key=f"save_file_{att['id']}",
                            )
                        except APIError as e:
                            st.error(f"Download failed: {e.detail}")
                with col_a3:
                    if can_upload:
                        if st.button("🗑️ Delete", key=f"del_att_{att['id']}"):
                            try:
                                client.delete_attachment(inc_id, att["id"])
                                st.success("Deleted attachment.")
                                st.rerun()
                            except APIError as e:
                                st.error(f"Delete failed: {e.detail}")
