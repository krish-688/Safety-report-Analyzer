"""Investigations and Corrective Actions (CAPA) router."""
import csv
from datetime import datetime
import io
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import (
    CorrectiveAction, Equipment, Incident, Investigation, PlantUnit, User,
)
from app.models.base import utcnow
from app.models.enums import ActionStatus, ActionType, UserRole, WorkflowStatus
from app.schemas.investigation import (
    ActionApproval, CorrectiveActionCreate, CorrectiveActionRead, CorrectiveActionUpdate,
    InvestigationCreate, InvestigationRead, InvestigationUpdate,
)
from app.services.audit_service import log_action
from app.services.incident_service import (
    INCIDENT_READ_ROLES, INCIDENT_WRITE_ROLES, check_incident_write_permission,
    get_incident_or_404, scope_incident_query,
)

router = APIRouter(tags=["investigations"])

Reader = Depends(require_roles(*INCIDENT_READ_ROLES))
Writer = Depends(require_roles(*INCIDENT_WRITE_ROLES))


def _build_investigation_read(inv: Investigation) -> InvestigationRead:
    return InvestigationRead(
        id=inv.id,
        incident_id=inv.incident_id,
        investigator_id=inv.investigator_id,
        investigator_name=inv.investigator.name if inv.investigator else None,
        assigned_by_id=inv.assigned_by_id,
        due_date=inv.due_date,
        evidence=inv.evidence,
        findings=inv.findings,
        verified_by_id=inv.verified_by_id,
        closed_at=inv.closed_at,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


def _build_action_read(action: CorrectiveAction) -> CorrectiveActionRead:
    inc = action.incident
    plant = inc.plant if inc else None
    return CorrectiveActionRead(
        id=action.id,
        incident_id=action.incident_id,
        incident_reference=inc.reference if inc else None,
        plant_id=inc.plant_id if inc else None,
        plant_name=plant.name if plant else None,
        investigation_id=action.investigation_id,
        action_type=action.action_type,
        description=action.description,
        owner_id=action.owner_id,
        owner_name=action.owner.name if action.owner else None,
        equipment_id=action.equipment_id,
        equipment_tag=action.equipment.tag if action.equipment else None,
        due_date=action.due_date,
        status=action.status,
        approved_by_id=action.approved_by_id,
        completed_at=action.completed_at,
        created_at=action.created_at,
    )


# --- Investigation Endpoints ---------------------------------------------------------------------


@router.get("/incidents/{incident_id}/investigation", response_model=InvestigationRead | None)
def get_incident_investigation(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    inc = get_incident_or_404(db, user, incident_id)
    inv = db.scalar(
        select(Investigation)
        .where(Investigation.incident_id == inc.id)
        .options(joinedload(Investigation.investigator))
    )
    if not inv:
        return None
    return _build_investigation_read(inv)


@router.post("/incidents/{incident_id}/investigation", response_model=InvestigationRead, status_code=status.HTTP_201_CREATED)
def start_or_create_investigation(
    incident_id: int,
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    existing = db.scalar(select(Investigation).where(Investigation.incident_id == inc.id))
    if existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "An investigation record already exists for this incident.",
        )

    # Validate investigator if specified
    if payload.investigator_id:
        inv_user = db.get(User, payload.investigator_id)
        if not inv_user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Investigator #{payload.investigator_id} not found.")

    inv = Investigation(
        incident_id=inc.id,
        investigator_id=payload.investigator_id or user.id,
        assigned_by_id=user.id,
        due_date=payload.due_date,
        evidence=payload.evidence,
        findings=payload.findings,
    )
    db.add(inv)

    if inc.status == WorkflowStatus.REPORTED:
        inc.status = WorkflowStatus.UNDER_INVESTIGATION

    log_action(db, user, "incident.investigation_started", "investigation", inc.id)
    db.commit()
    db.refresh(inv)

    return _build_investigation_read(inv)


@router.patch("/incidents/{incident_id}/investigation", response_model=InvestigationRead)
def update_investigation(
    incident_id: int,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    inv = db.scalar(select(Investigation).where(Investigation.incident_id == inc.id))
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No investigation record found for this incident.")

    if payload.investigator_id is not None:
        inv_user = db.get(User, payload.investigator_id)
        if not inv_user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Investigator #{payload.investigator_id} not found.")
        inv.investigator_id = payload.investigator_id
    if payload.due_date is not None:
        inv.due_date = payload.due_date
    if payload.evidence is not None:
        inv.evidence = payload.evidence
    if payload.findings is not None:
        inv.findings = payload.findings

    log_action(db, user, "incident.investigation_updated", "investigation", inv.id)
    db.commit()
    db.refresh(inv)

    return _build_investigation_read(inv)


@router.post("/incidents/{incident_id}/investigation/close", response_model=InvestigationRead)
def close_investigation(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SAFETY_MANAGER)),
):
    """Safety Manager closes and verifies the incident investigation."""
    inc = get_incident_or_404(db, user, incident_id)
    inv = db.scalar(select(Investigation).where(Investigation.incident_id == inc.id))
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation record missing.")

    inv.verified_by_id = user.id
    inv.closed_at = utcnow()
    inc.status = WorkflowStatus.CLOSED

    log_action(db, user, "incident.closed", "incident", inc.id, {"reference": inc.reference})
    db.commit()
    db.refresh(inv)

    return _build_investigation_read(inv)


# --- Corrective & Preventive Action (CAPA) Endpoints ----------------------------------------------


@router.get("/incidents/{incident_id}/actions", response_model=list[CorrectiveActionRead])
def list_incident_actions(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    inc = get_incident_or_404(db, user, incident_id)
    actions = db.scalars(
        select(CorrectiveAction)
        .where(CorrectiveAction.incident_id == inc.id)
        .options(
            joinedload(CorrectiveAction.owner),
            joinedload(CorrectiveAction.equipment),
            joinedload(CorrectiveAction.incident).joinedload(Incident.plant),
        )
        .order_by(CorrectiveAction.created_at.asc())
    ).all()

    return [_build_action_read(a) for a in actions]


@router.post("/incidents/{incident_id}/actions", response_model=CorrectiveActionRead, status_code=status.HTTP_201_CREATED)
def create_action(
    incident_id: int,
    payload: CorrectiveActionCreate,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    inv = db.scalar(select(Investigation).where(Investigation.incident_id == inc.id))

    if payload.owner_id:
        owner = db.get(User, payload.owner_id)
        if not owner:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Owner user #{payload.owner_id} not found.")

    if payload.equipment_id:
        eq = db.get(Equipment, payload.equipment_id)
        if not eq:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment #{payload.equipment_id} not found.")

    action = CorrectiveAction(
        incident_id=inc.id,
        investigation_id=inv.id if inv else None,
        action_type=payload.action_type,
        description=payload.description,
        owner_id=payload.owner_id or user.id,
        equipment_id=payload.equipment_id,
        due_date=payload.due_date,
        status=ActionStatus.PROPOSED,
    )
    db.add(action)

    # If incident was earlier in workflow, advance to Action Pending
    if inc.status in (WorkflowStatus.REPORTED, WorkflowStatus.UNDER_INVESTIGATION, WorkflowStatus.ROOT_CAUSE_IDENTIFIED):
        inc.status = WorkflowStatus.ACTION_PENDING

    log_action(db, user, "action.proposed", "corrective_action", inc.id)
    db.commit()
    db.refresh(action)

    return _build_action_read(action)


@router.get("/actions", response_model=list[CorrectiveActionRead])
def list_all_actions(
    status: ActionStatus | None = Query(None),
    plant_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    scoped_incidents = scope_incident_query(user, select(Incident.id))
    if plant_id is not None:
        scoped_incidents = scoped_incidents.where(Incident.plant_id == plant_id)

    stmt = (
        select(CorrectiveAction)
        .where(CorrectiveAction.incident_id.in_(scoped_incidents))
        .options(
            joinedload(CorrectiveAction.owner),
            joinedload(CorrectiveAction.equipment),
            joinedload(CorrectiveAction.incident).joinedload(Incident.plant),
        )
    )
    if status is not None:
        stmt = stmt.where(CorrectiveAction.status == status)

    actions = db.scalars(stmt.order_by(CorrectiveAction.due_date.asc())).all()
    return [_build_action_read(a) for a in actions]


@router.get("/actions/export-csv")
def export_actions_csv(
    status: ActionStatus | None = Query(None),
    plant_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    scoped_incidents = scope_incident_query(user, select(Incident.id))
    if plant_id is not None:
        scoped_incidents = scoped_incidents.where(Incident.plant_id == plant_id)

    stmt = (
        select(CorrectiveAction)
        .where(CorrectiveAction.incident_id.in_(scoped_incidents))
        .options(
            joinedload(CorrectiveAction.owner),
            joinedload(CorrectiveAction.equipment),
            joinedload(CorrectiveAction.incident).joinedload(Incident.plant),
        )
    )
    if status is not None:
        stmt = stmt.where(CorrectiveAction.status == status)

    actions = db.scalars(stmt.order_by(CorrectiveAction.due_date.asc())).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Action ID", "Incident Ref", "Plant", "Action Type", "Description",
        "Owner", "Equipment Tag", "Due Date", "Status", "Completed At"
    ])
    for a in actions:
        p_name = a.incident.plant.name if a.incident and a.incident.plant else ""
        inc_ref = a.incident.reference if a.incident else ""
        eq_tag = a.equipment.tag if a.equipment else ""
        owner_name = a.owner.name if a.owner else ""
        completed = a.completed_at.strftime("%Y-%m-%d %H:%M") if a.completed_at else ""
        writer.writerow([
            a.id, inc_ref, p_name, a.action_type.value, a.description,
            owner_name, eq_tag, a.due_date.isoformat(), a.status.value, completed
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="corrective_actions.csv"'},
    )


@router.post("/actions/{action_id}/approve", response_model=CorrectiveActionRead)
def approve_action(
    action_id: int,
    approval: ActionApproval,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PLANT_MANAGER, UserRole.SAFETY_MANAGER)),
):
    action = db.scalar(
        select(CorrectiveAction)
        .where(CorrectiveAction.id == action_id)
        .options(
            joinedload(CorrectiveAction.incident),
            joinedload(CorrectiveAction.owner),
            joinedload(CorrectiveAction.equipment),
        )
    )
    if not action:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found.")

    # Plant Manager can only approve actions for their own plant
    if user.role == UserRole.PLANT_MANAGER and user.plant_id != action.incident.plant_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Plant Managers can only approve actions for their own plant.",
        )

    if approval.approved:
        action.status = ActionStatus.APPROVED
        action.approved_by_id = user.id
        log_action(db, user, "action.approved", "corrective_action", action.id)
    else:
        action.status = ActionStatus.REJECTED
        log_action(db, user, "action.rejected", "corrective_action", action.id)

    db.commit()
    db.refresh(action)
    return _build_action_read(action)


@router.patch("/actions/{action_id}", response_model=CorrectiveActionRead)
def update_action(
    action_id: int,
    payload: CorrectiveActionUpdate,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    action = db.scalar(
        select(CorrectiveAction)
        .where(CorrectiveAction.id == action_id)
        .options(
            joinedload(CorrectiveAction.incident),
            joinedload(CorrectiveAction.owner),
            joinedload(CorrectiveAction.equipment),
        )
    )
    if not action:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found.")

    # Scoping check
    if user.role in (UserRole.PLANT_MANAGER, UserRole.SAFETY_OFFICER) and user.plant_id != action.incident.plant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found.")

    if payload.description is not None:
        action.description = payload.description
    if payload.owner_id is not None:
        action.owner_id = payload.owner_id
    if payload.due_date is not None:
        action.due_date = payload.due_date

    if payload.status is not None:
        action.status = payload.status
        if payload.status == ActionStatus.COMPLETED:
            action.completed_at = utcnow()

            # Check if all actions for this incident are completed
            all_actions = db.scalars(
                select(CorrectiveAction).where(CorrectiveAction.incident_id == action.incident_id)
            ).all()
            if all(a.status == ActionStatus.COMPLETED for a in all_actions):
                inc = action.incident
                if inc.status in (WorkflowStatus.ACTION_PENDING, WorkflowStatus.UNDER_INVESTIGATION):
                    inc.status = WorkflowStatus.VERIFICATION

    log_action(db, user, "action.updated", "corrective_action", action.id)
    db.commit()
    db.refresh(action)
    return _build_action_read(action)
