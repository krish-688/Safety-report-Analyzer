"""User Management view for System Administrator."""
import streamlit as st

from api_client import APIClient, APIError


def render_admin_users_page(client: APIClient, user: dict) -> None:
    st.title("👥 User Administration & Approvals")
    st.caption("Manage enterprise user access, assign plant roles, and approve new account registrations.")

    # Status tabs / filter
    sel_status = st.selectbox("Filter Users by Status", ["All", "Pending", "Active", "Inactive", "Rejected"])
    status_filter = None if sel_status == "All" else sel_status

    try:
        users_resp = client.list_users(params={"status": status_filter, "size": 100})
        users_list = users_resp.get("items", [])
    except APIError as e:
        st.error(f"Failed to fetch users: {e.detail}")
        users_list = []

    try:
        plants = client.get_plants()
        plant_options = {f"{p['name']} ({p['code']})": p["id"] for p in plants}
    except Exception:
        plant_options = {}

    st.markdown(f"**Total accounts found:** {len(users_list)}")

    if not users_list:
        st.info("No users match the selected status.")
        return

    for u in users_list:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 2])

            with col_info:
                st.markdown(f"### {u['name']}")
                st.caption(f"Email: **{u['email']}** · Status: **`{u['status']}`**")
                req_info = f"Requested: `{u.get('requested_role')}`" if u.get("requested_role") else ""
                plant_info = f"Plant #{u['plant_id']}" if u.get("plant_id") else "No assigned plant"
                st.markdown(f"Current Role: **`{u['role']}`** · {plant_info} · {req_info}")

            with col_actions:
                uid = u["id"]

                if u["status"] == "Pending":
                    st.markdown("**Pending Registration Approval**")
                    with st.expander(f"Review & Approve #{uid}"):
                        assigned_role = st.selectbox(
                            "Assign Role",
                            ["Safety Officer", "Plant Manager", "Safety Manager", "Management"],
                            key=f"role_sel_{uid}",
                        )
                        assigned_plant = st.selectbox(
                            "Assign Plant",
                            list(plant_options.keys()),
                            key=f"plant_sel_{uid}",
                        )
                        target_plant_id = plant_options.get(assigned_plant)

                        col_app, col_rej = st.columns(2)
                        with col_app:
                            if st.button("Approve", key=f"appr_btn_{uid}", type="primary", use_container_width=True):
                                try:
                                    client.approve_user(uid, role=assigned_role, plant_id=target_plant_id)
                                    st.success(f"Approved {u['name']}!")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Approval error: {e.detail}")
                        with col_rej:
                            if st.button("Reject", key=f"rej_btn_{uid}", use_container_width=True):
                                try:
                                    client.reject_user(uid)
                                    st.warning(f"Rejected registration for {u['name']}.")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Reject error: {e.detail}")

                elif u["status"] == "Active" and u["id"] != user["id"]:
                    col_deact, col_pw, col_edit = st.columns(3)
                    with col_deact:
                        if st.button("Deactivate", key=f"deact_{uid}"):
                            try:
                                client.deactivate_user(uid)
                                st.rerun()
                            except APIError as e:
                                st.error(e.detail)
                    with col_pw:
                        with st.popover("Reset Password"):
                            new_pw = st.text_input("New Password", type="password", key=f"newpw_{uid}")
                            if st.button("Save Password", key=f"savepw_{uid}"):
                                try:
                                    client.reset_password(uid, new_pw)
                                    st.success("Password reset successfully!")
                                except APIError as e:
                                    st.error(e.detail)
                    with col_edit:
                        with st.popover("Edit Role/Plant"):
                            all_roles = ["Safety Officer", "Plant Manager", "Safety Manager", "Management", "Admin"]
                            cur_role = u.get("role", "Safety Officer")
                            edit_role = st.selectbox(
                                "Role",
                                all_roles,
                                index=all_roles.index(cur_role) if cur_role in all_roles else 0,
                                key=f"edit_role_{uid}",
                            )
                            # Plant options
                            plant_labels = ["No Plant Assigned"] + list(plant_options.keys())
                            cur_p_id = u.get("plant_id")
                            cur_p_idx = 0
                            for idx, (p_lbl, pid) in enumerate(plant_options.items(), 1):
                                if pid == cur_p_id:
                                    cur_p_idx = idx
                                    break
                            edit_plant_sel = st.selectbox("Plant", plant_labels, index=cur_p_idx, key=f"edit_plant_{uid}")
                            new_p_id = plant_options.get(edit_plant_sel) if edit_plant_sel != "No Plant Assigned" else None

                            if st.button("Update User", key=f"update_u_{uid}", type="primary"):
                                try:
                                    client.update_user(uid, role=edit_role, plant_id=new_p_id)
                                    st.success(f"Updated {u['name']}.")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Update failed: {e.detail}")

                elif u["status"] == "Inactive":
                    if st.button("Reactivate Account", key=f"react_{uid}"):
                        try:
                            client.activate_user(uid)
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)
