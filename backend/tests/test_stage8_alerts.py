"""Stage 8 tests: Alerts, Notifications, Background Scans, and Threshold Tuning."""
from datetime import date, timedelta
from tests.conftest import API


def test_alert_lifecycle_and_unread_count(client, auth, seeded):
    # Safety Manager or Plant Manager already has seeded alerts
    headers_sm = auth("safety_manager")

    r_alerts = client.get(f"{API}/alerts", headers=headers_sm)
    assert r_alerts.status_code == 200
    alerts = r_alerts.json()
    assert isinstance(alerts, list)

    r_unread = client.get(f"{API}/alerts/unread-count", headers=headers_sm)
    assert r_unread.status_code == 200
    initial_unread = r_unread.json()["unread_count"]
    assert isinstance(initial_unread, int)

    # If there are alerts, test marking one read
    if alerts:
        target_alert = alerts[0]
        aid = target_alert["id"]

        r_read = client.post(f"{API}/alerts/{aid}/read", headers=headers_sm)
        assert r_read.status_code == 200
        assert r_read.json()["is_read"] is True

        # Test mark all read
        r_all = client.post(f"{API}/alerts/mark-all-read", headers=headers_sm)
        assert r_all.status_code == 200

        # Unread count should now be 0
        r_unread_after = client.get(f"{API}/alerts/unread-count", headers=headers_sm)
        assert r_unread_after.json()["unread_count"] == 0


def test_overdue_scan_triggers(client, auth, seeded):
    p1 = seeded["plant_ids"][0]
    headers_so1 = auth("so1")

    # Create an incident with an overdue investigation
    r_inc = client.post(
        f"{API}/incidents",
        headers=headers_so1,
        json={
            "title": "Incident with overdue investigation",
            "occurred_at": "2026-09-01T10:00:00",
            "plant_id": p1,
            "incident_type": "Procedure Deviation",
            "description": "Overdue investigation test incident description.",
            "severity": "Medium",
        },
    )
    assert r_inc.status_code == 201
    inc_id = r_inc.json()["id"]

    # Start investigation with past due date
    past_due = (date.today() - timedelta(days=5)).isoformat()
    r_inv = client.post(
        f"{API}/incidents/{inc_id}/investigation",
        headers=headers_so1,
        json={"due_date": past_due, "findings": "Overdue investigation ongoing"},
    )
    assert r_inv.status_code == 201

    # Trigger scan
    r_scan = client.post(f"{API}/alerts/scan", headers=headers_so1)
    assert r_scan.status_code == 200
    data = r_scan.json()
    assert "new_alerts_created" in data
    assert data["new_alerts_created"] >= 1

    # Investigator so1 should have received an INVESTIGATION_OVERDUE alert
    r_my_alerts = client.get(f"{API}/alerts?unread_only=true", headers=headers_so1)
    assert r_my_alerts.status_code == 200
    my_alerts = r_my_alerts.json()
    assert any(
        a.get("alert_type") in ("Investigation Overdue", "investigation_overdue") and a.get("incident_id") == inc_id
        for a in my_alerts
    )


def test_threshold_management(client, auth):
    admin_headers = auth("admin")
    so1_headers = auth("so1")

    # List thresholds
    r_list = client.get(f"{API}/alerts/thresholds", headers=admin_headers)
    assert r_list.status_code == 200
    thresholds = r_list.json()
    assert len(thresholds) >= 4
    keys = [t["key"] for t in thresholds]
    assert "equipment_incident_count" in keys

    # Safety Officer cannot update thresholds (RBAC)
    r_forbidden = client.patch(
        f"{API}/alerts/thresholds/equipment_incident_count",
        headers=so1_headers,
        json={"value": 5},
    )
    assert r_forbidden.status_code == 403

    # Admin updates threshold
    r_upd = client.patch(
        f"{API}/alerts/thresholds/equipment_incident_count",
        headers=admin_headers,
        json={"value": 5},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["value"] == 5

    # Update invalid key
    r_404 = client.patch(
        f"{API}/alerts/thresholds/non_existent_key",
        headers=admin_headers,
        json={"value": 10},
    )
    assert r_404.status_code == 404
