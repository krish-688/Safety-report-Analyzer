"""Stage 7 tests: Investigation lifecycle, CAPA actions, Plant Manager approvals, and closure."""
from datetime import date, timedelta
from tests.conftest import API


def test_investigation_creation_and_scoping(client, auth, seeded):
    p1 = seeded["plant_ids"][0]
    p2 = seeded["plant_ids"][1]

    # Create fresh incident in Plant 1
    r_inc = client.post(
        f"{API}/incidents",
        headers=auth("so1"),
        json={
            "title": "Investigation Test Incident",
            "occurred_at": "2026-10-01T12:00:00",
            "plant_id": p1,
            "incident_type": "Equipment Failure",
            "description": "Centrifugal pump P-101 vibration excursion and casing overheat.",
            "severity": "High",
        },
    )
    assert r_inc.status_code == 201
    inc_id = r_inc.json()["id"]
    assert r_inc.json()["status"] == "Reported"

    # Plant 2 Safety Officer cannot start investigation on Plant 1 incident
    r_foreign = client.post(
        f"{API}/incidents/{inc_id}/investigation",
        headers=auth("so2"),
        json={"findings": "Unauthorized cross plant investigation"},
    )
    assert r_foreign.status_code == 404

    # Plant 1 Safety Officer starts investigation
    r_inv = client.post(
        f"{API}/incidents/{inc_id}/investigation",
        headers=auth("so1"),
        json={
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
            "findings": "Initial 5-why reveals lubrication starvation.",
            "evidence": "Oil reservoir empty, bearing temperature logged 112 C.",
        },
    )
    assert r_inv.status_code == 201
    inv_data = r_inv.json()
    assert inv_data["incident_id"] == inc_id
    assert "lubrication starvation" in inv_data["findings"]

    # Verify incident status advanced to 'Under Investigation'
    r_detail = client.get(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_detail.status_code == 200
    assert r_detail.json()["status"] == "Under Investigation"

    # Update investigation findings
    r_upd = client.patch(
        f"{API}/incidents/{inc_id}/investigation",
        headers=auth("so1"),
        json={"findings": "Finalized findings: seal flushed with contaminated lube oil."},
    )
    assert r_upd.status_code == 200
    assert "contaminated lube oil" in r_upd.json()["findings"]


def test_capa_action_lifecycle_and_plant_manager_approval(client, auth, seeded):
    p1 = seeded["plant_ids"][0]

    # Create incident in Plant 1
    r_inc = client.post(
        f"{API}/incidents",
        headers=auth("so1"),
        json={
            "title": "CAPA Approval Test Incident",
            "occurred_at": "2026-10-01T13:00:00",
            "plant_id": p1,
            "incident_type": "Loss of Containment",
            "description": "Flange leak during line pressurisation.",
            "severity": "Medium",
        },
    )
    assert r_inc.status_code == 201
    inc_id = r_inc.json()["id"]

    # Propose corrective action
    r_act = client.post(
        f"{API}/incidents/{inc_id}/actions",
        headers=auth("so1"),
        json={
            "action_type": "Corrective",
            "description": "Replace gasket and retorque studs to revised standard.",
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    assert r_act.status_code == 201
    act_data = r_act.json()
    act_id = act_data["id"]
    assert act_data["status"] == "Proposed"

    # Incident status advanced to 'Action Pending'
    r_detail = client.get(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_detail.json()["status"] == "Action Pending"

    # Plant Manager 2 (foreign plant) CANNOT approve Plant 1 action
    r_foreign_appr = client.post(
        f"{API}/actions/{act_id}/approve",
        headers=auth("pm2"),
        json={"approved": True},
    )
    assert r_foreign_appr.status_code == 403

    # Safety Officer CANNOT approve actions (Plant Manager or Safety Manager only)
    r_so_appr = client.post(
        f"{API}/actions/{act_id}/approve",
        headers=auth("so1"),
        json={"approved": True},
    )
    assert r_so_appr.status_code == 403

    # Plant Manager 1 approves the action
    r_pm1_appr = client.post(
        f"{API}/actions/{act_id}/approve",
        headers=auth("pm1"),
        json={"approved": True},
    )
    assert r_pm1_appr.status_code == 200
    assert r_pm1_appr.json()["status"] == "Approved"

    # Update to In Progress
    r_prog = client.patch(
        f"{API}/actions/{act_id}",
        headers=auth("so1"),
        json={"status": "In Progress"},
    )
    assert r_prog.status_code == 200
    assert r_prog.json()["status"] == "In Progress"

    # Mark Completed
    r_comp = client.patch(
        f"{API}/actions/{act_id}",
        headers=auth("so1"),
        json={"status": "Completed"},
    )
    assert r_comp.status_code == 200
    assert r_comp.json()["status"] == "Completed"

    # Since all actions are completed, incident status transitions to 'Verification'
    r_verif = client.get(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_verif.json()["status"] == "Verification"

    # Start investigation so it can be formally closed
    client.post(
        f"{API}/incidents/{inc_id}/investigation",
        headers=auth("so1"),
        json={"findings": "All corrective actions verified complete."},
    )

    # Safety Officer CANNOT close incident
    r_close_so = client.post(f"{API}/incidents/{inc_id}/investigation/close", headers=auth("so1"))
    assert r_close_so.status_code == 403

    # Safety Manager closes incident
    r_close_sm = client.post(f"{API}/incidents/{inc_id}/investigation/close", headers=auth("safety_manager"))
    assert r_close_sm.status_code == 200
    assert r_close_sm.json()["closed_at"] is not None

    r_final = client.get(f"{API}/incidents/{inc_id}", headers=auth("safety_manager"))
    assert r_final.json()["status"] == "Closed"
