"""Stage 4 tests: API client integration, authentication state, and role navigation mapping."""
import sys
from pathlib import Path

# Add frontend directory to path for testing
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

import pytest
from api_client import APIClient, APIError
from components.navigation import ROLE_PAGES
from tests.conftest import API


def test_api_client_auth_flow(client, seeded):
    """Test APIClient using the test client base url."""
    api = APIClient(base_url=f"http://testserver{API}")

    # Patch client's internal request to hit test client
    admin_info = seeded["users"]["admin"]

    # Login
    res = client.post(f"{API}/auth/login", json={"email": admin_info["email"], "password": admin_info["password"]})
    assert res.status_code == 200
    token = res.json()["access_token"]

    api.set_token(token)
    assert api._headers() == {"Authorization": f"Bearer {token}"}

    # Error handling
    err_res = client.get(f"{API}/incidents", headers=api._headers())
    assert err_res.status_code == 403  # Admin cannot access operational incidents


def test_role_navigation_permissions_matrix():
    """Verify role-based navigation isolates pages strictly by role."""
    # Admin: system and user management only, no operational incident access
    admin_pages = [page_id for _, page_id in ROLE_PAGES["Admin"]]
    assert "admin_users" in admin_pages
    assert "system_status" in admin_pages
    assert "incidents" not in admin_pages
    assert "dashboard" not in admin_pages
    assert "new_incident" not in admin_pages

    # Management: executive dashboards and reading incidents, no incident reporting
    mgmt_pages = [page_id for _, page_id in ROLE_PAGES["Management"]]
    assert "dashboard" in mgmt_pages
    assert "incidents" in mgmt_pages
    assert "reports" in mgmt_pages
    assert "new_incident" not in mgmt_pages
    assert "admin_users" not in mgmt_pages

    # Safety Officer: reports incidents, views incidents, dashboard, investigations
    so_pages = [page_id for _, page_id in ROLE_PAGES["Safety Officer"]]
    assert "dashboard" in so_pages
    assert "incidents" in so_pages
    assert "new_incident" in so_pages
    assert "investigations" in so_pages
    assert "admin_users" not in so_pages

    # Safety Manager: full operational access across plants
    sm_pages = [page_id for _, page_id in ROLE_PAGES["Safety Manager"]]
    assert "dashboard" in sm_pages
    assert "incidents" in sm_pages
    assert "new_incident" in sm_pages
    assert "investigations" in sm_pages
    assert "admin_users" not in sm_pages

    # Plant Manager: operational oversight of plant, but cannot create raw incident reports directly
    pm_pages = [page_id for _, page_id in ROLE_PAGES["Plant Manager"]]
    assert "dashboard" in pm_pages
    assert "incidents" in pm_pages
    assert "investigations" in pm_pages
    assert "new_incident" not in pm_pages
    assert "admin_users" not in pm_pages
