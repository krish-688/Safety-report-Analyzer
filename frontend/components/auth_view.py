"""Authentication views: Login, Registration, and Demo Credentials Selector."""
import streamlit as st

from api_client import APIClient, APIError


def render_auth_page(client: APIClient) -> None:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #E65100; margin-bottom: 0.2rem;">🛡️ SafeTrack AI</h1>
            <p style="color: #64748B; font-size: 1.1rem;">
                Safety Incident Prediction & Root Cause Analysis Platform
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

        with tab_login:
            _render_login_form(client)

        with tab_register:
            _render_register_form(client)

        st.markdown("---")
        _render_demo_accounts_expander(client)


def _render_login_form(client: APIClient) -> None:
    with st.form("login_form"):
        email = st.text_input("Corporate Email", placeholder="user@safety.local").strip()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return

            try:
                res = client.login(email=email, password=password)
                st.session_state.token = res["access_token"]
                st.session_state.user = res["user"]
                st.toast(f"Welcome back, {res['user']['name']}!", icon="👋")
                st.rerun()
            except APIError as e:
                if "locked" in e.detail.lower():
                    st.error(f"🔒 Account Locked: {e.detail}")
                elif "pending" in e.detail.lower():
                    st.warning(f"⏳ Pending Approval: {e.detail}")
                elif "rejected" in e.detail.lower():
                    st.error(f"🚫 Access Denied: {e.detail}")
                elif "inactive" in e.detail.lower():
                    st.error(f"⚠️ Account Inactive: {e.detail}")
                else:
                    st.error(f"Authentication failed: {e.detail}")


def _render_register_form(client: APIClient) -> None:
    try:
        options = client.get_register_options()
        roles = options.get("roles", [])
        plants = options.get("plants", [])
    except Exception as e:
        st.error(f"Failed to load registration options: {e}")
        roles, plants = [], []

    with st.form("register_form"):
        name = st.text_input("Full Name", placeholder="e.g. Jane Doe").strip()
        email = st.text_input("Work Email", placeholder="jane.doe@safety.local").strip()
        password = st.text_input("Password", type="password", help="At least 8 characters, with 1 uppercase, 1 lowercase, and 1 number.")

        role_options = [r for r in roles if r != "Admin"]
        selected_role = st.selectbox("Requested Role", role_options if role_options else ["Safety Officer", "Plant Manager"])

        plant_dict = {f"{p['name']} ({p['code']})": p["id"] for p in plants}
        plant_names = ["-- Select Assigned Plant --"] + list(plant_dict.keys())
        selected_plant_name = st.selectbox("Assigned Plant (Required for Plant Roles)", plant_names)

        st.caption("ℹ️ Accounts are created in **Pending** status and must be activated by an Administrator.")
        submitted = st.form_submit_button("Submit Registration", use_container_width=True)

        if submitted:
            if not name or not email or not password:
                st.error("Please fill in all required fields.")
                return

            preferred_plant_id = None
            if selected_plant_name != "-- Select Assigned Plant --":
                preferred_plant_id = plant_dict[selected_plant_name]

            if selected_role in ("Safety Officer", "Plant Manager") and not preferred_plant_id:
                st.error("Please select an assigned plant for plant-bound roles.")
                return

            try:
                client.register(
                    name=name,
                    email=email,
                    password=password,
                    requested_role=selected_role,
                    preferred_plant_id=preferred_plant_id,
                )
                st.success("✅ Registration submitted successfully! Please wait for an Administrator to approve your account.")
            except APIError as e:
                st.error(f"Registration failed: {e.detail}")


def _render_demo_accounts_expander(client: APIClient) -> None:
    with st.expander("⚡ Quick Demo Sign-In (Click to Log In)", expanded=False):
        st.markdown("Select a preset demo user to log in instantly:")

        demo_users = [
            ("👑 System Admin", "admin@safety.local", "Admin@12345", "Manages users, approvals & thresholds"),
            ("🔍 Safety Manager", "safety.manager@safety.local", "Demo@12345", "Global visibility across all plants"),
            ("📊 Management", "management@safety.local", "Demo@12345", "Executive read-only dashboards"),
            ("🏭 Plant 1 Manager (ECP)", "plant.manager@safety.local", "Demo@12345", "Ethylene Cracker Plant Manager"),
            ("👷 Plant 1 Safety Officer", "officer@safety.local", "Demo@12345", "Ethylene Cracker Safety Officer"),
            ("🏭 Plant 2 Manager (PLU)", "plant.manager2@safety.local", "Demo@12345", "Polymer Unit Manager"),
            ("👷 Plant 2 Safety Officer", "officer2@safety.local", "Demo@12345", "Polymer Unit Safety Officer"),
        ]

        for label, email, password, note in demo_users:
            col_btn, col_info = st.columns([1.5, 2.5])
            with col_btn:
                if st.button(label, key=f"demo_login_{email}", use_container_width=True):
                    try:
                        res = client.login(email=email, password=password)
                        st.session_state.token = res["access_token"]
                        st.session_state.user = res["user"]
                        st.toast(f"Logged in as {res['user']['name']}", icon="✅")
                        st.rerun()
                    except APIError as e:
                        st.error(f"Login failed: {e.detail}")
            with col_info:
                st.caption(f"**{email}** — *{note}*")
