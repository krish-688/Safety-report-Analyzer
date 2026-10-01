"""Stage 10 tests: Reports Engine, PDF Dossier Generation, and Scoped CSV Exports."""
from tests.conftest import API


def test_pdf_dossier_export(client, auth, seeded):
    p1 = seeded["plant_ids"][0]
    p2 = seeded["plant_ids"][1]
    so1_headers = auth("so1")
    so2_headers = auth("so2")
    admin_headers = auth("admin")

    # Create an incident in Plant 1 with full details
    r_inc = client.post(
        f"{API}/incidents",
        headers=so1_headers,
        json={
            "title": "Stage 10 Dossier Test Incident",
            "occurred_at": "2026-09-15T08:30:00",
            "plant_id": p1,
            "incident_type": "Loss of Containment",
            "description": "High pressure flange leak on naphtha hydrotreater feed pump P-101A.",
            "severity": "High",
            "damage_details": "Gasket blowout, 20L naphtha release onto concrete pad.",
            "immediate_actions": "Pump isolated, foam blanket applied, fire team dispatched.",
        },
    )
    assert r_inc.status_code == 201
    inc_id = r_inc.json()["id"]

    # Start investigation
    r_inv = client.post(
        f"{API}/incidents/{inc_id}/investigation",
        headers=so1_headers,
        json={
            "findings": "Bolt torque insufficient after turnaround gasket change.",
            "evidence": "Flange inspection report #FL-2026-99.",
        },
    )
    assert r_inv.status_code == 201

    # Add corrective action
    r_act = client.post(
        f"{API}/incidents/{inc_id}/actions",
        headers=so1_headers,
        json={
            "action_type": "Corrective",
            "description": "Retorque all critical flanges on unit and update torque register.",
            "due_date": "2026-10-30",
        },
    )
    assert r_act.status_code == 201

    # Plant 1 Safety Officer exports PDF dossier
    r_pdf = client.get(f"{API}/incidents/{inc_id}/export-pdf", headers=so1_headers)
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert "Incident_Dossier_" in r_pdf.headers.get("content-disposition", "")
    pdf_bytes = r_pdf.content
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    # Plant 2 Safety Officer cannot export dossier for Plant 1 incident (404 opaque scoping)
    r_foreign = client.get(f"{API}/incidents/{inc_id}/export-pdf", headers=so2_headers)
    assert r_foreign.status_code == 404

    # Admin cannot access operational incident dossier (403 or 404)
    r_admin = client.get(f"{API}/incidents/{inc_id}/export-pdf", headers=admin_headers)
    assert r_admin.status_code in (403, 404)


def test_actions_csv_export_and_scoping(client, auth, seeded):
    so1_headers = auth("so1")
    sm_headers = auth("safety_manager")

    # Safety Officer exports actions CSV
    r_csv = client.get(f"{API}/actions/export-csv", headers=so1_headers)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    content = r_csv.text
    assert "Action ID,Incident Ref,Plant,Action Type,Description" in content

    # Safety Manager exports global actions CSV
    r_global = client.get(f"{API}/actions/export-csv", headers=sm_headers)
    assert r_global.status_code == 200
    assert len(r_global.text) >= len(content)


def test_incidents_csv_export(client, auth):
    sm_headers = auth("safety_manager")
    r_csv = client.get(f"{API}/incidents/export-csv?severity=High", headers=sm_headers)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    assert "Reference,Title,Occurred At" in r_csv.text
