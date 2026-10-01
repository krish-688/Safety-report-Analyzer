"""Stage 6 tests: Plant equipment listing, text analysis endpoint, and incident management flow."""
from tests.conftest import API


def test_plant_equipment_listing(client, auth, seeded):
    p1 = seeded["plant_ids"][0]
    r = client.get(f"{API}/plants/{p1}/equipment", headers=auth("so1"))
    assert r.status_code == 200
    eq_list = r.json()
    assert len(eq_list) > 0
    for eq in eq_list:
        assert eq["plant_id"] == p1
        assert "tag" in eq
        assert "name" in eq
        assert "equipment_type" in eq

    # 404 for invalid plant
    assert client.get(f"{API}/plants/99999/equipment", headers=auth("so1")).status_code == 404


def test_analyze_raw_text_endpoint(client, auth):
    payload = {
        "title": "Severe hydrocarbon release from seal failure",
        "text": "The mechanical seal on compressor K-101 failed catastrophically releasing hydrocarbon cloud into the unit. Vibration was high and maintenance overdue.",
        "incident_type": "Loss of Containment",
        "severity": "High",
        "injuries": 0,
    }
    r = client.post(f"{API}/incidents/analyze-text", headers=auth("so1"), json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["risk_confidence"] > 0.70
    assert len(data["result"]["root_causes"]) >= 1

    cause = data["result"]["root_causes"][0]
    assert "category" in cause
    assert "evidence" in cause
    assert "confidence" in cause


def test_incident_full_management_lifecycle(client, auth, seeded):
    p1 = seeded["plant_ids"][0]

    # 1. Fetch equipment to link
    eqs = client.get(f"{API}/plants/{p1}/equipment", headers=auth("so1")).json()
    assert len(eqs) >= 2
    eq1, eq2 = eqs[0], eqs[1]

    # 2. Create incident with equipment
    payload = {
        "title": "Stage 6 Lifecycle Incident Test",
        "occurred_at": "2026-10-01T14:30:00",
        "plant_id": p1,
        "incident_type": "Equipment Failure",
        "description": "Exchanger tube bundle leak occurred during heavy production rate. Vibration and thermal stress detected.",
        "severity": "Medium",
        "injuries": 0,
        "equipment_ids": [eq1["id"]],
    }
    r_create = client.post(f"{API}/incidents", headers=auth("so1"), json=payload)
    assert r_create.status_code == 201
    inc = r_create.json()
    inc_id = inc["id"]
    assert len(inc["equipment"]) == 1
    assert inc["status"] == "Reported"

    # 3. Update equipment and description
    patch_payload = {
        "description": "Updated description with further inspection details on tube bundle.",
        "equipment_ids": [eq1["id"], eq2["id"]],
    }
    r_patch = client.patch(f"{API}/incidents/{inc_id}", headers=auth("so1"), json=patch_payload)
    assert r_patch.status_code == 200
    patched = r_patch.json()
    assert len(patched["equipment"]) == 2
    assert "tube bundle" in patched["description"]

    # 4. Run NLP Analysis
    r_nlp = client.post(f"{API}/incidents/{inc_id}/analyze", headers=auth("so1"), json={})
    assert r_nlp.status_code == 200
    nlp_data = r_nlp.json()
    assert len(nlp_data["root_causes"]) >= 1

    # 5. Add Manual Root Cause
    r_add_rc = client.post(
        f"{API}/incidents/{inc_id}/root-causes",
        headers=auth("so1"),
        json={"action": "add", "root_cause_id": 1, "evidence": "Operator error during ramp-up rate adjustment."},
    )
    assert r_add_rc.status_code == 200

    # 6. Verify status advanced to 'Root Cause Identified'
    r_detail = client.get(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_detail.status_code == 200
    assert r_detail.json()["status"] == "Root Cause Identified"
