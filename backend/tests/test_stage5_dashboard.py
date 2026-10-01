"""Stage 5 tests: Dashboard KPI summary, monthly trends, Pareto causes, and equipment watchlist."""
from datetime import datetime, timedelta

import pytest
from tests.conftest import API


def test_dashboard_summary_scoping(client, auth, seeded):
    # Safety Manager sees all plants
    r_sm = client.get(f"{API}/dashboard/summary", headers=auth("safety_manager"))
    assert r_sm.status_code == 200
    sm_data = r_sm.json()
    assert sm_data["total_incidents"] >= 300
    assert sm_data["total_incidents"] == sm_data["critical_risk"] + sm_data["high_risk"] + sm_data["medium_risk"] + sm_data["low_risk"] + sm_data["unanalyzed_risk"]

    # Management sees all plants
    r_mgmt = client.get(f"{API}/dashboard/summary", headers=auth("management"))
    assert r_mgmt.status_code == 200
    assert r_mgmt.json()["total_incidents"] == sm_data["total_incidents"]

    # Plant 1 Safety Officer sees only Plant 1 incidents
    r_so1 = client.get(f"{API}/dashboard/summary", headers=auth("so1"))
    assert r_so1.status_code == 200
    so1_data = r_so1.json()
    assert 0 < so1_data["total_incidents"] < sm_data["total_incidents"]

    # Admin has NO access to operational dashboard
    r_admin = client.get(f"{API}/dashboard/summary", headers=auth("admin"))
    assert r_admin.status_code == 403


def test_dashboard_summary_date_filtering(client, auth):
    h = auth("safety_manager")
    r_all = client.get(f"{API}/dashboard/summary", headers=h)
    assert r_all.status_code == 200
    total_all = r_all.json()["total_incidents"]

    # Filter to very recent (last 30 days)
    recent_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
    r_recent = client.get(f"{API}/dashboard/summary", headers=h, params={"from_date": recent_date})
    assert r_recent.status_code == 200
    total_recent = r_recent.json()["total_incidents"]
    assert 0 <= total_recent < total_all


def test_monthly_trends(client, auth):
    h = auth("safety_manager")
    r = client.get(f"{API}/dashboard/trends", headers=h, params={"months": 12})
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    for item in items:
        assert "month" in item
        assert item["total"] == item["low"] + item["medium"] + item["high"] + item["critical"]


def test_root_cause_pareto(client, auth):
    h = auth("safety_manager")
    r = client.get(f"{API}/dashboard/pareto-causes", headers=h)
    assert r.status_code == 200
    pareto_items = r.json()
    assert len(pareto_items) == 5  # 5 standard root cause categories
    # Ordered descending
    counts = [p["count"] for p in pareto_items]
    assert counts == sorted(counts, reverse=True)
    # Final cumulative percentage should be 100%
    assert pareto_items[-1]["cumulative_percentage"] == 100.0


def test_equipment_watchlist(client, auth):
    h = auth("safety_manager")
    r = client.get(f"{API}/dashboard/equipment-watch", headers=h, params={"limit": 5})
    assert r.status_code == 200
    watchlist = r.json()
    assert len(watchlist) == 5
    # Seed data deliberately generated "hot" equipment with ≥3 incidents
    assert any(item["threshold_exceeded"] for item in watchlist)


def test_plant_distribution(client, auth):
    # Safety Manager sees all 3 plants
    r_sm = client.get(f"{API}/dashboard/plant-distribution", headers=auth("safety_manager"))
    assert r_sm.status_code == 200
    assert len(r_sm.json()) == 3

    # Safety Officer 1 sees only Plant 1
    r_so1 = client.get(f"{API}/dashboard/plant-distribution", headers=auth("so1"))
    assert r_so1.status_code == 200
    assert len(r_so1.json()) == 1
