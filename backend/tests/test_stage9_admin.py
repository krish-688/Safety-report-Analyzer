"""Stage 9 tests: Admin management of plants, equipment, audit logs, and user configuration."""
from tests.conftest import API


def test_admin_plant_management(client, auth, seeded):
    admin_headers = auth("admin")
    sm_headers = auth("safety_manager")

    # Non-admin cannot create plant
    r_forbidden = client.post(
        f"{API}/plants",
        headers=sm_headers,
        json={"name": "Forbidden Plant", "code": "FB-01"},
    )
    assert r_forbidden.status_code == 403

    # Admin creates plant
    r_create = client.post(
        f"{API}/plants",
        headers=admin_headers,
        json={
            "name": "Ras Tanura Aromatics Complex",
            "code": "RT-AC",
            "location": "Ras Tanura Industrial Area",
            "is_active": True,
        },
    )
    assert r_create.status_code == 201
    plant_data = r_create.json()
    p_id = plant_data["id"]
    assert plant_data["code"] == "RT-AC"
    assert plant_data["name"] == "Ras Tanura Aromatics Complex"

    # Duplicate code rejected
    r_dup = client.post(
        f"{API}/plants",
        headers=admin_headers,
        json={"name": "Another Plant", "code": "RT-AC"},
    )
    assert r_dup.status_code == 400

    # Admin updates plant
    r_upd = client.patch(
        f"{API}/plants/{p_id}",
        headers=admin_headers,
        json={"location": "Ras Tanura Pier 3", "is_active": False},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["is_active"] is False
    assert r_upd.json()["location"] == "Ras Tanura Pier 3"

    # Admin lists all plants including inactive
    r_all = client.get(f"{API}/plants/all", headers=admin_headers)
    assert r_all.status_code == 200
    assert any(p["id"] == p_id for p in r_all.json())


def test_admin_equipment_management(client, auth, seeded):
    admin_headers = auth("admin")
    so1_headers = auth("so1")
    p1 = seeded["plant_ids"][0]

    # Non-admin cannot create equipment
    r_forbidden = client.post(
        f"{API}/plants/{p1}/equipment",
        headers=so1_headers,
        json={"plant_id": p1, "tag": "P-FORBIDDEN", "name": "Illegal Pump", "equipment_type": "Pump"},
    )
    assert r_forbidden.status_code == 403

    # Admin creates equipment
    r_create = client.post(
        f"{API}/plants/{p1}/equipment",
        headers=admin_headers,
        json={
            "plant_id": p1,
            "tag": "E-999-ST9",
            "name": "Stage 9 Quench Reboiler",
            "equipment_type": "Heat Exchanger",
            "is_active": True,
        },
    )
    assert r_create.status_code == 201
    eq_data = r_create.json()
    eq_id = eq_data["id"]
    assert eq_data["tag"] == "E-999-ST9"

    # Duplicate tag rejected
    r_dup = client.post(
        f"{API}/plants/{p1}/equipment",
        headers=admin_headers,
        json={
            "plant_id": p1,
            "tag": "E-999-ST9",
            "name": "Duplicate Equipment",
            "equipment_type": "Heat Exchanger",
        },
    )
    assert r_dup.status_code == 400

    # Admin updates equipment
    r_upd = client.patch(
        f"{API}/equipment/{eq_id}",
        headers=admin_headers,
        json={"name": "Stage 9 Quench Reboiler Modified", "is_active": False},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["name"] == "Stage 9 Quench Reboiler Modified"
    assert r_upd.json()["is_active"] is False

    # List equipment with filters
    r_list = client.get(f"{API}/equipment?search=Stage%209", headers=admin_headers)
    assert r_list.status_code == 200
    items = r_list.json()
    assert len(items) >= 1
    assert items[0]["id"] == eq_id


def test_admin_audit_logs(client, auth):
    admin_headers = auth("admin")
    so1_headers = auth("so1")

    # Non-admin cannot read audit logs
    r_forbidden = client.get(f"{API}/audit-logs", headers=so1_headers)
    assert r_forbidden.status_code == 403

    # Admin can view audit logs
    r_logs = client.get(f"{API}/audit-logs?limit=50", headers=admin_headers)
    assert r_logs.status_code == 200
    logs = r_logs.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1

    actions = [l["action"] for l in logs]
    # Check common actions exist
    assert any("user" in a or "incident" in a or "seed" in a or "plant" in a or "equipment" in a for a in actions)


def test_admin_user_update_and_protection(client, auth, seeded):
    admin_headers = auth("admin")
    so1 = seeded["users"]["so1"]
    p2 = seeded["plant_ids"][1]

    # Admin updates Safety Officer's plant to plant 2
    r_upd = client.patch(
        f"{API}/users/{so1['id']}",
        headers=admin_headers,
        json={"plant_id": p2},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["plant_id"] == p2

    # Attempting to assign plant-bound role with no plant raises 422
    r_invalid = client.patch(
        f"{API}/users/{so1['id']}",
        headers=admin_headers,
        json={"role": "Safety Officer", "plant_id": None},
    )
    assert r_invalid.status_code == 422
