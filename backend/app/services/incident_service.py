"""Incident access rules and business logic.

EVERY incident query must go through scope_incident_query().
"""
import csv
import io
from fastapi import HTTPException, status
from sqlalchemy import Select, false, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Attachment, Equipment, Incident, IncidentEquipment, IncidentRootCause, PlantUnit, User,
)
from app.models.enums import UserRole

# Roles that see all plants.
ALL_PLANT_ROLES = {UserRole.SAFETY_MANAGER, UserRole.MANAGEMENT}
# Roles restricted to their own plant/unit.
OWN_PLANT_ROLES = {UserRole.PLANT_MANAGER, UserRole.SAFETY_OFFICER}
# Roles allowed to read incidents at all (Admin is deliberately excluded).
INCIDENT_READ_ROLES = ALL_PLANT_ROLES | OWN_PLANT_ROLES

# Roles allowed to create and update incidents.
INCIDENT_WRITE_ROLES = {UserRole.SAFETY_OFFICER, UserRole.SAFETY_MANAGER}


def scope_incident_query(user: User, stmt: Select | None = None) -> Select:
    """Restrict an incident SELECT to what `user` may see. The single source of truth."""
    stmt = select(Incident) if stmt is None else stmt
    if user.role in ALL_PLANT_ROLES:
        return stmt
    if user.role in OWN_PLANT_ROLES and user.plant_id is not None:
        return stmt.where(Incident.plant_id == user.plant_id)
    return stmt.where(false())  # Admin, or a plant-bound user without a plant: nothing


def get_incident_or_404(db: Session, user: User, incident_id: int) -> Incident:
    """Out-of-scope incidents return 404 (not 403) so their existence is not revealed."""
    incident = db.scalars(
        scope_incident_query(user)
        .where(Incident.id == incident_id)
        .options(
            joinedload(Incident.plant),
            joinedload(Incident.created_by),
            joinedload(Incident.equipment_links).joinedload(IncidentEquipment.equipment),
            joinedload(Incident.root_causes).joinedload(IncidentRootCause.root_cause),
            joinedload(Incident.attachments).joinedload(Attachment.uploaded_by),
        )
    ).first()
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found.")
    return incident


def check_incident_write_permission(user: User, plant_id: int) -> None:
    """Ensure user is authorized to create/modify an incident for the specified plant."""
    if user.role == UserRole.SAFETY_MANAGER:
        return
    if user.role == UserRole.SAFETY_OFFICER:
        if user.plant_id != plant_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Safety Officers can only create or modify incidents for their assigned plant.",
            )
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"Your role ({user.role.value}) is not allowed to modify incidents.",
    )


def generate_incident_reference(db: Session, year: int) -> str:
    """Generate the next sequential reference for a given year: INC-YYYY-0001, etc."""
    prefix = f"INC-{year}-"
    refs = db.scalars(
        select(Incident.reference).where(Incident.reference.like(f"{prefix}%"))
    ).all()
    max_num = 0
    for ref in refs:
        try:
            num = int(ref[len(prefix):])
            if num > max_num:
                max_num = num
        except (ValueError, TypeError):
            continue
    return f"INC-{year}-{max_num + 1:04d}"


def build_incident_detail(incident: Incident) -> dict:
    """Convert an Incident ORM entity with relationships into a dictionary for IncidentDetail schema."""
    equipment_list = []
    for link in incident.equipment_links:
        if link.equipment:
            equipment_list.append({
                "equipment_id": link.equipment.id,
                "tag": link.equipment.tag,
                "name": link.equipment.name,
                "equipment_type": link.equipment.equipment_type,
            })

    root_causes_list = []
    for rc in incident.root_causes:
        root_causes_list.append({
            "id": rc.id,
            "incident_id": rc.incident_id,
            "root_cause_id": rc.root_cause_id,
            "root_cause_code": rc.root_cause.code if rc.root_cause else None,
            "root_cause_name": rc.root_cause.name if rc.root_cause else None,
            "source": rc.source,
            "confidence": rc.confidence,
            "evidence": rc.evidence,
            "review_status": rc.review_status,
            "reviewed_by_id": rc.reviewed_by_id,
            "analysis_id": rc.analysis_id,
            "created_at": rc.created_at,
        })

    attachments_list = []
    for att in incident.attachments:
        attachments_list.append({
            "id": att.id,
            "incident_id": att.incident_id,
            "filename": att.filename,
            "content_type": att.content_type,
            "size_bytes": att.size_bytes,
            "uploaded_by_id": att.uploaded_by_id,
            "uploaded_by_name": att.uploaded_by.name if att.uploaded_by else None,
            "uploaded_at": att.uploaded_at,
        })

    return {
        "id": incident.id,
        "reference": incident.reference,
        "title": incident.title,
        "occurred_at": incident.occurred_at,
        "plant_id": incident.plant_id,
        "plant_name": incident.plant.name if incident.plant else None,
        "incident_type": incident.incident_type,
        "description": incident.description,
        "severity": incident.severity,
        "injuries": incident.injuries,
        "damage_details": incident.damage_details,
        "immediate_actions": incident.immediate_actions,
        "risk_level": incident.risk_level,
        "risk_confidence": incident.risk_confidence,
        "status": incident.status,
        "created_by_id": incident.created_by_id,
        "created_by_name": incident.created_by.name if incident.created_by else None,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "equipment": equipment_list,
        "root_causes": root_causes_list,
        "attachments": attachments_list,
    }


def generate_incidents_csv(incidents: list[Incident]) -> str:
    """Generate a clean CSV string from a list of incidents."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference",
        "Title",
        "Occurred At",
        "Plant",
        "Incident Type",
        "Severity",
        "Risk Level",
        "Risk Confidence",
        "Status",
        "Injuries",
        "Created At",
    ])
    for inc in incidents:
        plant_name = inc.plant.name if inc.plant else f"Plant #{inc.plant_id}"
        writer.writerow([
            inc.reference,
            inc.title,
            inc.occurred_at.isoformat() if inc.occurred_at else "",
            plant_name,
            inc.incident_type,
            inc.severity.value if inc.severity else "",
            inc.risk_level.value if inc.risk_level else "",
            f"{inc.risk_confidence:.2f}" if inc.risk_confidence is not None else "",
            inc.status.value if inc.status else "",
            inc.injuries,
            inc.created_at.isoformat() if inc.created_at else "",
        ])
    return output.getvalue()
