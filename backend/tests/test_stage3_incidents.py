import io
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import Equipment, Incident, PlantUnit, RootCause
from app.models.enums import ReviewStatus, RiskLevel, Severity, WorkflowStatus
from tests.conftest import API


def test_safety_officer_can_create_incident_in_own_plant(client, auth, seeded, db):
    so1_plant = seeded["users"]["so1"]["plant_id"]
    eq = db.scalar(select(Equipment).where(Equipment.plant_id == so1_plant))

    payload = {
        "title": "High pressure alarm trip on pump",
        "occurred_at": "2026-10-01T08:00:00",
        "incident_type": "Equipment Failure",
        "description": "The centrifugal pump experienced severe vibration and tripped on high pressure alarm. Operator followed emergency procedure.",
        "severity": "Medium",
        "injuries": 0,
        "immediate_actions": "Pump isolated, backup line engaged.",
        "equipment_ids": [eq.id] if eq else [],
    }

    r = client.post(f"{API}/incidents", headers=auth("so1"), json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["plant_id"] == so1_plant
    assert data["status"] == "Reported"
    assert data["reference"].startswith("INC-2026-")
    assert len(data["equipment"]) == (1 if eq else 0)


def test_safety_officer_cannot_create_incident_for_other_plant(client, auth, seeded):
    other_plant = seeded["plant_ids"][1]
    payload = {
        "title": "Cross plant test",
        "occurred_at": "2026-10-01T08:00:00",
        "plant_id": other_plant,
        "incident_type": "Near Miss",
        "description": "Attempting to create incident in another plant unit without permission.",
        "severity": "Low",
    }
    r = client.post(f"{API}/incidents", headers=auth("so1"), json=payload)
    assert r.status_code == 403


def test_safety_manager_can_create_for_any_plant(client, auth, seeded):
    plant = seeded["plant_ids"][2]
    payload = {
        "title": "Safety manager global report",
        "occurred_at": "2026-10-01T09:00:00",
        "plant_id": plant,
        "incident_type": "Process Upset",
        "description": "Temperature excursion during reactor feed changeover. Interlock bypass was active.",
        "severity": "High",
        "injuries": 0,
    }
    r = client.post(f"{API}/incidents", headers=auth("safety_manager"), json=payload)
    assert r.status_code == 201
    assert r.json()["plant_id"] == plant


def test_incident_create_rejects_unauthorized_roles(client, auth, seeded):
    payload = {
        "title": "Unauthorized attempt",
        "occurred_at": "2026-10-01T08:00:00",
        "incident_type": "Near Miss",
        "description": "A test to ensure read-only or admin users cannot create incidents.",
    }
    for key in ("admin", "management", "pm1"):
        r = client.post(f"{API}/incidents", headers=auth(key), json=payload)
        assert r.status_code == 403


def test_update_and_delete_incident(client, auth, seeded, db):
    so1_plant = seeded["users"]["so1"]["plant_id"]
    payload = {
        "title": "Temporary incident to update and delete",
        "occurred_at": "2026-10-01T10:00:00",
        "incident_type": "Near Miss",
        "description": "Minor leak noticed near flange during routine inspection and immediately tightened.",
        "severity": "Low",
    }
    r = client.post(f"{API}/incidents", headers=auth("so1"), json=payload)
    assert r.status_code == 201
    inc_id = r.json()["id"]

    # Patch incident
    patch_payload = {
        "title": "Updated incident title",
        "severity": "Medium",
    }
    r_patch = client.patch(f"{API}/incidents/{inc_id}", headers=auth("so1"), json=patch_payload)
    assert r_patch.status_code == 200
    assert r_patch.json()["title"] == "Updated incident title"
    assert r_patch.json()["severity"] == "Medium"

    # Delete incident
    r_del = client.delete(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_del.status_code == 200
    # Verification that it is gone
    assert client.get(f"{API}/incidents/{inc_id}", headers=auth("so1")).status_code == 404


def test_filtering_and_csv_export(client, auth, seeded):
    h = auth("safety_manager")

    # Filter by severity
    r = client.get(f"{API}/incidents", headers=h, params={"severity": "High"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["severity"] == "High" for i in items)

    # Search filter
    r_search = client.get(f"{API}/incidents", headers=h, params={"search": "valve"})
    assert r_search.status_code == 200
    assert r_search.json()["total"] > 0

    # CSV Export
    r_csv = client.get(f"{API}/incidents/export-csv", headers=h)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    assert "Reference,Title,Occurred At" in r_csv.text

    # Scoped CSV export for plant officer
    r_csv_so = client.get(f"{API}/incidents/export-csv", headers=auth("so1"))
    assert r_csv_so.status_code == 200
    p1_name = "Ethylene Cracker Plant"
    lines = r_csv_so.text.strip().split("\n")
    # All non-header lines should belong to Plant 1
    for line in lines[1:]:
        assert p1_name in line or "Plant #1" in line


def test_attachment_upload_and_download(client, auth, seeded, db):
    so1_plant = seeded["users"]["so1"]["plant_id"]
    inc_id = db.scalar(select(Incident.id).where(Incident.plant_id == so1_plant))

    file_content = b"Safety inspection report content: all seals checked."
    files = {"file": ("inspection_note.txt", io.BytesIO(file_content), "text/plain")}

    # Upload attachment
    r_up = client.post(f"{API}/incidents/{inc_id}/attachments", headers=auth("so1"), files=files)
    assert r_up.status_code == 201
    att_data = r_up.json()
    att_id = att_data["id"]
    assert att_data["filename"] == "inspection_note.txt"
    assert att_data["size_bytes"] == len(file_content)

    # List attachments
    r_list = client.get(f"{API}/incidents/{inc_id}/attachments", headers=auth("so1"))
    assert r_list.status_code == 200
    assert any(a["id"] == att_id for a in r_list.json())

    # Download attachment
    r_down = client.get(f"{API}/incidents/{inc_id}/attachments/{att_id}/download", headers=auth("so1"))
    assert r_down.status_code == 200
    assert r_down.content == file_content

    # Delete attachment
    r_del = client.delete(f"{API}/incidents/{inc_id}/attachments/{att_id}", headers=auth("so1"))
    assert r_del.status_code == 200


def test_nlp_analyze_and_root_cause_review(client, auth, seeded, db):
    so1_plant = seeded["users"]["so1"]["plant_id"]

    # Create an incident with strong process/equipment cues
    payload = {
        "title": "Severe hydrocarbon seal leak and high vibration on compressor",
        "occurred_at": "2026-10-01T11:00:00",
        "incident_type": "Loss of Containment",
        "description": "Mechanical seal failed on compressor K-101 releasing flammable gas. Vibration readings had been trending high and preventive maintenance was overdue. Operator bypassed interlock.",
        "severity": "High",
        "injuries": 0,
        "damage_details": "Seal ring completely destroyed.",
    }
    r = client.post(f"{API}/incidents", headers=auth("so1"), json=payload)
    assert r.status_code == 201
    inc_id = r.json()["id"]

    # Run NLP Analysis
    r_nlp = client.post(f"{API}/incidents/{inc_id}/analyze", headers=auth("so1"), json={})
    assert r_nlp.status_code == 200
    nlp_data = r_nlp.json()
    assert nlp_data["risk_level"] in ("HIGH", "CRITICAL")
    assert nlp_data["risk_confidence"] > 0.70
    assert len(nlp_data["root_causes"]) >= 1

    suggested_cause = nlp_data["root_causes"][0]
    assert suggested_cause["review_status"] == "Suggested"

    # Accept root cause
    r_accept = client.post(
        f"{API}/incidents/{inc_id}/root-causes",
        headers=auth("so1"),
        json={"action": "accept", "incident_root_cause_id": suggested_cause["id"]},
    )
    assert r_accept.status_code == 200
    accepted = next(c for c in r_accept.json() if c["id"] == suggested_cause["id"])
    assert accepted["review_status"] == "Accepted"

    # Verify workflow status updated to 'Root Cause Identified'
    r_detail = client.get(f"{API}/incidents/{inc_id}", headers=auth("so1"))
    assert r_detail.status_code == 200
    assert r_detail.json()["status"] == "Root Cause Identified"

    # Add a manual root cause
    all_causes = db.scalars(select(RootCause)).all()
    another_cause = next(c for c in all_causes if c.id != suggested_cause["root_cause_id"])

    r_manual = client.post(
        f"{API}/incidents/{inc_id}/root-causes",
        headers=auth("so1"),
        json={
            "action": "add",
            "root_cause_id": another_cause.id,
            "evidence": "Operator confirmed additional human factor contribution.",
        },
    )
    assert r_manual.status_code == 200
    manual_entries = [c for c in r_manual.json() if c["source"] == "Manual"]
    assert len(manual_entries) >= 1
    assert manual_entries[0]["review_status"] == "Accepted"
