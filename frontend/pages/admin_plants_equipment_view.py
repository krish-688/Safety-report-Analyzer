"""Admin Plants & Equipment Management View."""
import streamlit as st

from api_client import APIClient, APIError


EQUIPMENT_TYPES = [
    "Centrifugal Pump",
    "Positive Displacement Pump",
    "Compressor",
    "Pressure Vessel",
    "Distillation Column",
    "Storage Tank",
    "Heat Exchanger",
    "Reactor",
    "Furnace / Boiler",
    "Control Valve",
    "Relief Valve (PSV)",
    "Piping & Flange",
    "Instrument / Transmitter",
    "Electrical Switchgear",
]


def render_admin_plants_equipment_page(client: APIClient, user: dict) -> None:
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h1 style="color: #0F172A; margin: 0; font-size: 1.8rem;">🏭 Plants & Equipment Administration</h1>
            <p style="color: #64748B; margin: 0; font-size: 0.95rem;">
                Configure petrochemical refining units, operating facilities, and tagged equipment assets.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_plants, tab_eq = st.tabs(["🏭 Plant Units", "⚙️ Equipment Inventory"])

    # =========================================================================
    # TAB 1: Plants & Units
    # =========================================================================
    with tab_plants:
        col_list, col_add = st.columns([3, 2])

        with col_list:
            st.subheader("Registered Plant Facilities")
            try:
                plants = client.list_all_plants()
            except APIError as e:
                st.error(f"Failed to fetch plants: {e.detail}")
                plants = []

            if not plants:
                st.info("No plants found.")
            else:
                for p in plants:
                    pid = p["id"]
                    is_act = p.get("is_active", True)
                    status_badge = (
                        '<span style="background-color: #DCFCE7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">ACTIVE</span>'
                        if is_act
                        else '<span style="background-color: #FEE2E2; color: #991B1B; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">INACTIVE</span>'
                    )

                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 0.9rem; border-radius: 8px; margin-bottom: 0.6rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div>
                                        <span style="font-weight: 700; color: #0F172A; font-size: 1.05rem;">{p['name']}</span>
                                        <span style="color: #64748B; font-size: 0.85rem; margin-left: 0.5rem; font-family: monospace;">({p['code']})</span>
                                    </div>
                                    <div>{status_badge}</div>
                                </div>
                                <div style="color: #475569; font-size: 0.85rem; margin-top: 0.3rem;">
                                    📍 Location: {p.get('location') or 'Not specified'} · Plant #{pid}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        with st.expander(f"Edit Plant #{pid} ({p['code']})"):
                            edit_name = st.text_input("Plant Name", value=p["name"], key=f"edit_p_name_{pid}")
                            edit_code = st.text_input("Plant Code", value=p["code"], key=f"edit_p_code_{pid}")
                            edit_loc = st.text_input("Location", value=p.get("location") or "", key=f"edit_p_loc_{pid}")
                            edit_act = st.checkbox("Facility Active", value=is_act, key=f"edit_p_act_{pid}")

                            if st.button("Save Plant Changes", key=f"save_p_{pid}", type="primary"):
                                try:
                                    client.update_plant(
                                        pid,
                                        {
                                            "name": edit_name,
                                            "code": edit_code,
                                            "location": edit_loc,
                                            "is_active": edit_act,
                                        },
                                    )
                                    st.toast(f"Plant #{pid} updated successfully.", icon="✅")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Failed to update plant: {e.detail}")

        with col_add:
            st.subheader("➕ Add New Facility")
            with st.form("new_plant_form"):
                new_p_name = st.text_input("Plant Name *", placeholder="e.g. South Complex Hydrocracker")
                new_p_code = st.text_input("Plant Code *", placeholder="e.g. SC-HC")
                new_p_loc = st.text_input("Physical Location", placeholder="e.g. Jubail Industrial Zone Sector 4")
                new_p_active = st.checkbox("Active Immediately", value=True)

                submit_plant = st.form_submit_button("Create Plant", type="primary", use_container_width=True)
                if submit_plant:
                    if not new_p_name or not new_p_code:
                        st.error("Name and Code are required.")
                    else:
                        try:
                            created = client.create_plant(
                                name=new_p_name,
                                code=new_p_code,
                                location=new_p_loc or None,
                                is_active=new_p_active,
                            )
                            st.toast(f"Created plant {created['name']} ({created['code']})", icon="🎉")
                            st.rerun()
                        except APIError as e:
                            st.error(f"Creation failed: {e.detail}")

    # =========================================================================
    # TAB 2: Equipment Inventory
    # =========================================================================
    with tab_eq:
        try:
            all_plants = client.get_plants()
            plant_id_to_name = {p["id"]: f"{p['name']} ({p['code']})" for p in all_plants}
        except Exception:
            all_plants = []
            plant_id_to_name = {}

        # Filters and creation toolbar
        f1, f2, f3 = st.columns([2, 2, 3])
        with f1:
            filter_plant = st.selectbox(
                "Filter by Plant",
                options=["All Plants"] + list(plant_id_to_name.keys()),
                format_func=lambda x: "All Plants" if x == "All Plants" else plant_id_to_name.get(x, f"Plant #{x}"),
            )
        with f2:
            eq_type_filter = st.selectbox("Equipment Type", options=["All Types"] + EQUIPMENT_TYPES)
        with f3:
            eq_search = st.text_input("Search Equipment Tag or Name", placeholder="e.g. P-101 or Centrifugal")

        plant_arg = None if filter_plant == "All Plants" else filter_plant
        type_arg = None if eq_type_filter == "All Types" else eq_type_filter

        try:
            equipment_items = client.list_equipment(
                plant_id=plant_arg,
                equipment_type=type_arg,
                search=eq_search or None,
                limit=300,
            )
        except APIError as e:
            st.error(f"Failed to fetch equipment: {e.detail}")
            equipment_items = []

        col_eq_list, col_eq_add = st.columns([3, 2])

        with col_eq_list:
            st.markdown(f"**Found {len(equipment_items)} equipment assets**")
            if not equipment_items:
                st.info("No equipment matches the filter criteria.")
            else:
                for eq in equipment_items[:50]:  # render top 50 in view
                    eid = eq["id"]
                    is_active = eq.get("is_active", True)
                    p_name = plant_id_to_name.get(eq["plant_id"], f"Plant #{eq['plant_id']}")

                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 0.5rem;">
                                <div style="display: flex; justify-content: space-between;">
                                    <div>
                                        <span style="font-weight: 700; color: #E65100; font-family: monospace; font-size: 1rem;">{eq['tag']}</span>
                                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.5rem;">{eq['name']}</span>
                                    </div>
                                    <div>
                                        <span style="background-color: {'#DCFCE7' if is_active else '#FEE2E2'}; color: {'#166534' if is_active else '#991B1B'}; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">
                                            {'ACTIVE' if is_active else 'INACTIVE'}
                                        </span>
                                    </div>
                                </div>
                                <div style="color: #64748B; font-size: 0.8rem; margin-top: 0.2rem;">
                                    Type: <b>{eq['equipment_type']}</b> · Facility: <b>{p_name}</b>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        with st.expander(f"Edit {eq['tag']} Details"):
                            e_name = st.text_input("Name", value=eq["name"], key=f"eq_name_{eid}")
                            e_tag = st.text_input("Tag", value=eq["tag"], key=f"eq_tag_{eid}")
                            e_type = st.selectbox(
                                "Type",
                                options=EQUIPMENT_TYPES,
                                index=EQUIPMENT_TYPES.index(eq["equipment_type"]) if eq["equipment_type"] in EQUIPMENT_TYPES else 0,
                                key=f"eq_type_{eid}",
                            )
                            e_act = st.checkbox("Asset In Service", value=is_active, key=f"eq_act_{eid}")

                            if st.button("Save Equipment", key=f"save_eq_{eid}", type="primary"):
                                try:
                                    client.update_equipment(
                                        eid,
                                        {
                                            "name": e_name,
                                            "tag": e_tag,
                                            "equipment_type": e_type,
                                            "is_active": e_act,
                                        },
                                    )
                                    st.toast(f"Asset {e_tag} updated successfully.", icon="✅")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Failed to update equipment: {e.detail}")

        with col_eq_add:
            st.subheader("➕ Register New Equipment")
            if not all_plants:
                st.warning("Please create at least one plant facility first.")
            else:
                with st.form("new_equipment_form"):
                    target_plant = st.selectbox(
                        "Assigned Plant Unit *",
                        options=list(plant_id_to_name.keys()),
                        format_func=lambda x: plant_id_to_name.get(x, f"Plant #{x}"),
                    )
                    new_tag = st.text_input("Equipment Tag *", placeholder="e.g. P-401A, E-205, V-102")
                    new_name = st.text_input("Equipment Name *", placeholder="e.g. Crude Charge Pump A")
                    new_type = st.selectbox("Equipment Category *", options=EQUIPMENT_TYPES)
                    new_active = st.checkbox("Active / In Service", value=True)

                    submit_eq = st.form_submit_button("Register Equipment", type="primary", use_container_width=True)
                    if submit_eq:
                        if not new_tag or not new_name:
                            st.error("Equipment Tag and Name are required.")
                        else:
                            try:
                                created_eq = client.create_equipment(
                                    plant_id=target_plant,
                                    tag=new_tag,
                                    name=new_name,
                                    equipment_type=new_type,
                                    is_active=new_active,
                                )
                                st.toast(f"Registered {created_eq['tag']} ({created_eq['name']})", icon="🎉")
                                st.rerun()
                            except APIError as e:
                                st.error(f"Registration failed: {e.detail}")
