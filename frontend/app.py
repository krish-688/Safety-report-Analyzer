"""SafeTrack AI - Main Streamlit Application Entrypoint.

Thin client frontend communicating with the FastAPI backend via api_client.py.
Handles session authentication, user profile state, and role-based routing.
"""
import os
import sys
from pathlib import Path

# Add frontend directory to sys.path
FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

import streamlit as st

from api_client import APIClient, APIError
from components.auth_view import render_auth_page
from components.navigation import render_sidebar
from pages.admin_plants_equipment_view import render_admin_plants_equipment_page
from pages.admin_users_view import render_admin_users_page
from pages.analyze_report_view import render_analyze_report_page
from pages.dashboard_view import render_dashboard_page
from pages.incidents_view import render_incidents_page
from pages.investigations_view import render_investigations_page
from pages.new_incident_view import render_new_incident_page
from pages.alerts_view import render_alerts_page
from pages.reports_view import render_reports_page
from pages.system_status_view import render_system_status_page

# Configure Streamlit App
st.set_page_config(
    page_title="SafeTrack AI - Petrochemical HSE Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "active_page" not in st.session_state:
    st.session_state.active_page = None

# Initialize API Client
API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")
client = APIClient(base_url=API_URL, token=st.session_state.token)


def main():
    # If unauthenticated, show login/register views
    if not st.session_state.token or not st.session_state.user:
        render_auth_page(client)
        return

    # Verify session token validity
    try:
        current_user = client.get_me()
        st.session_state.user = current_user
    except APIError as e:
        if e.status_code == 401:
            st.warning("Your session has expired. Please sign in again.")
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.active_page = None
            st.rerun()
            return
        else:
            st.error(f"Error checking user session: {e.detail}")

    user = st.session_state.user

    # Render Navigation Sidebar
    active_page = render_sidebar(client, user)

    # Route to Selected Page
    if active_page == "dashboard":
        render_dashboard_page(client, user)
    elif active_page == "incidents":
        render_incidents_page(client, user)
    elif active_page == "new_incident":
        render_new_incident_page(client, user)
    elif active_page == "analyze_report":
        render_analyze_report_page(client, user)
    elif active_page == "investigations":
        render_investigations_page(client, user)
    elif active_page == "alerts":
        render_alerts_page(client, user)
    elif active_page == "reports":
        render_reports_page(client, user)
    elif active_page == "admin_users":
        render_admin_users_page(client, user)
    elif active_page == "admin_plants_equipment":
        render_admin_plants_equipment_page(client, user)
    elif active_page == "system_status":
        render_system_status_page(client, user)
    else:
        render_dashboard_page(client, user)


if __name__ == "__main__":
    main()
