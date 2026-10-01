"""Incident management router: CRUD, filtering, CSV export, attachments, and NLP analysis."""
import os
from datetime import datetime
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.deps import require_roles
from app.db.session import get_db
from app.models import (
    Attachment, Equipment, Incident, IncidentEquipment, IncidentRootCause, NLPAnalysis, PlantUnit, RootCause, User,
)
from app.models.enums import CauseSource, ReviewStatus, RiskLevel, Severity, UserRole, WorkflowStatus
from app.schemas.common import Page
from app.schemas.incident import (
    AnalyzeTextRequest, AnalyzeTextResponse, AttachmentRead, IncidentCreate, IncidentDetail, IncidentListItem,
    IncidentRootCauseRead, IncidentUpdate, NLPAnalyzeRequest, NLPAnalysisRead, RootCauseReviewAction,
)
from app.services.audit_service import log_action
from app.services.incident_service import (
    INCIDENT_READ_ROLES, INCIDENT_WRITE_ROLES, build_incident_detail,
    check_incident_write_permission, generate_incident_reference, generate_incidents_csv,
    get_incident_or_404, scope_incident_query,
)
from app.services.alert_service import check_equipment_incident_thresholds, check_incident_risk_alerts
from app.services.nlp_service import analyze_raw_text, analyze_report
from app.services.report_service import generate_incident_pdf_dossier

router = APIRouter(prefix="/incidents", tags=["incidents"])

Reader = Depends(require_roles(*INCIDENT_READ_ROLES))
Writer = Depends(require_roles(*INCIDENT_WRITE_ROLES))


@router.get("", response_model=Page[IncidentListItem])
def list_incidents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    plant_id: int | None = Query(None),
    severity: Severity | None = Query(None),
    risk_level: RiskLevel | None = Query(None),
    status: WorkflowStatus | None = Query(None),
    incident_type: str | None = Query(None),
    equipment_id: int | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    stmt = scope_incident_query(user)

    if plant_id is not None:
        stmt = stmt.where(Incident.plant_id == plant_id)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if risk_level is not None:
        stmt = stmt.where(Incident.risk_level == risk_level)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if incident_type is not None:
        stmt = stmt.where(Incident.incident_type == incident_type)
    if from_date is not None:
        stmt = stmt.where(Incident.occurred_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Incident.occurred_at <= to_date)
    if equipment_id is not None:
        stmt = stmt.join(IncidentEquipment, IncidentEquipment.incident_id == Incident.id).where(
            IncidentEquipment.equipment_id == equipment_id
        )
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            Incident.title.ilike(term) | Incident.reference.ilike(term) | Incident.description.ilike(term)
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(joinedload(Incident.plant))
        .order_by(Incident.occurred_at.desc(), Incident.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    items = [
        IncidentListItem(
            id=r.id,
            reference=r.reference,
            title=r.title,
            occurred_at=r.occurred_at,
            plant_id=r.plant_id,
            plant_name=r.plant.name if r.plant else None,
            incident_type=r.incident_type,
            severity=r.severity,
            risk_level=r.risk_level,
            risk_confidence=r.risk_confidence,
            status=r.status,
            injuries=r.injuries,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return Page[IncidentListItem](items=items, total=total, page=page, size=size)


@router.get("/export-csv")
def export_incidents_csv(
    plant_id: int | None = Query(None),
    severity: Severity | None = Query(None),
    risk_level: RiskLevel | None = Query(None),
    status: WorkflowStatus | None = Query(None),
    incident_type: str | None = Query(None),
    equipment_id: int | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    stmt = scope_incident_query(user)

    if plant_id is not None:
        stmt = stmt.where(Incident.plant_id == plant_id)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if risk_level is not None:
        stmt = stmt.where(Incident.risk_level == risk_level)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if incident_type is not None:
        stmt = stmt.where(Incident.incident_type == incident_type)
    if from_date is not None:
        stmt = stmt.where(Incident.occurred_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Incident.occurred_at <= to_date)
    if equipment_id is not None:
        stmt = stmt.join(IncidentEquipment, IncidentEquipment.incident_id == Incident.id).where(
            IncidentEquipment.equipment_id == equipment_id
        )
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            Incident.title.ilike(term) | Incident.reference.ilike(term) | Incident.description.ilike(term)
        )

    incidents = db.scalars(
        stmt.options(joinedload(Incident.plant))
        .order_by(Incident.occurred_at.desc(), Incident.id.desc())
        .limit(2000)
    ).all()

    csv_data = generate_incidents_csv(incidents)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="incidents.csv"'},
    )


@router.post("", response_model=IncidentDetail, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    # Determine plant
    if user.role == UserRole.SAFETY_OFFICER:
        if payload.plant_id is not None and payload.plant_id != user.plant_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Safety Officers can only report incidents for their assigned plant.",
            )
        plant_id = user.plant_id
    else:  # Safety Manager
        if payload.plant_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "plant_id is required for Safety Managers.",
            )
        plant_id = payload.plant_id

    plant = db.get(PlantUnit, plant_id)
    if not plant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{plant_id} not found.")

    # Validate equipment
    equipment_records = []
    if payload.equipment_ids:
        for eid in payload.equipment_ids:
            eq = db.get(Equipment, eid)
            if not eq:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment #{eid} not found.")
            if eq.plant_id != plant_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Equipment {eq.tag} belongs to a different plant.",
                )
            equipment_records.append(eq)

    # Generate sequential reference
    ref = generate_incident_reference(db, payload.occurred_at.year)

    inc = Incident(
        reference=ref,
        title=payload.title,
        occurred_at=payload.occurred_at,
        plant_id=plant_id,
        incident_type=payload.incident_type,
        description=payload.description,
        severity=payload.severity,
        injuries=payload.injuries,
        damage_details=payload.damage_details,
        immediate_actions=payload.immediate_actions,
        status=WorkflowStatus.REPORTED,
        created_by_id=user.id,
    )
    db.add(inc)
    db.flush()

    for eq in equipment_records:
        db.add(IncidentEquipment(incident_id=inc.id, equipment_id=eq.id))

    log_action(db, user, "incident.created", "incident", inc.id, {"reference": inc.reference})
    db.commit()
    db.refresh(inc)

    # Check for equipment repeat threshold & risk alerts
    check_equipment_incident_thresholds(db, inc)
    if inc.risk_level:
        check_incident_risk_alerts(db, inc)
    db.commit()

    return build_incident_detail(get_incident_or_404(db, user, inc.id))


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    incident = get_incident_or_404(db, user, incident_id)
    return build_incident_detail(incident)


@router.get("/{incident_id}/export-pdf")
def export_incident_pdf(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    incident = get_incident_or_404(db, user, incident_id)
    pdf_bytes = generate_incident_pdf_dossier(db, incident)
    filename = f"Incident_Dossier_{incident.reference}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{incident_id}", response_model=IncidentDetail)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    if payload.title is not None:
        inc.title = payload.title
    if payload.occurred_at is not None:
        inc.occurred_at = payload.occurred_at
    if payload.incident_type is not None:
        inc.incident_type = payload.incident_type
    if payload.description is not None:
        inc.description = payload.description
    if payload.severity is not None:
        inc.severity = payload.severity
    if payload.injuries is not None:
        inc.injuries = payload.injuries
    if payload.damage_details is not None:
        inc.damage_details = payload.damage_details
    if payload.immediate_actions is not None:
        inc.immediate_actions = payload.immediate_actions
    if payload.status is not None:
        inc.status = payload.status

    if payload.equipment_ids is not None:
        # Clear existing equipment links
        for link in list(inc.equipment_links):
            db.delete(link)
        db.flush()
        # Add new links
        for eid in payload.equipment_ids:
            eq = db.get(Equipment, eid)
            if not eq:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment #{eid} not found.")
            if eq.plant_id != inc.plant_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Equipment {eq.tag} belongs to a different plant.",
                )
            db.add(IncidentEquipment(incident_id=inc.id, equipment_id=eq.id))

    log_action(db, user, "incident.updated", "incident", inc.id, {"reference": inc.reference})
    db.commit()
    db.refresh(inc)

    # Check alert conditions
    check_equipment_incident_thresholds(db, inc)
    if inc.risk_level:
        check_incident_risk_alerts(db, inc)
    db.commit()

    return build_incident_detail(get_incident_or_404(db, user, inc.id))


@router.delete("/{incident_id}")
def delete_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    # Safety Officer can only delete if status is REPORTED
    if user.role == UserRole.SAFETY_OFFICER and inc.status != WorkflowStatus.REPORTED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Safety Officers can only delete incidents that are still in 'Reported' status.",
        )

    ref = inc.reference
    log_action(db, user, "incident.deleted", "incident", inc.id, {"reference": ref})
    db.delete(inc)
    db.commit()

    return {"message": "Incident deleted successfully.", "id": incident_id, "reference": ref}


# --- Attachments ---------------------------------------------------------------------------------


@router.post("/{incident_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    incident_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File extension '{ext}' is not allowed. Allowed: {settings.ALLOWED_UPLOAD_EXTENSIONS}",
        )

    # Read content and check size limit
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_MB} MB.",
        )

    # Save to disk
    folder = Path(settings.UPLOAD_DIR) / f"incident_{inc.id}"
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    target_path = folder / safe_name
    with open(target_path, "wb") as f:
        f.write(content)

    stored_relative = f"incident_{inc.id}/{safe_name}"
    att = Attachment(
        incident_id=inc.id,
        filename=Path(file.filename).name,
        stored_path=stored_relative,
        content_type=file.content_type,
        size_bytes=len(content),
        uploaded_by_id=user.id,
    )
    db.add(att)
    db.flush()

    log_action(
        db, user, "incident.attachment_added", "attachment", att.id,
        {"incident_id": inc.id, "filename": att.filename},
    )
    db.commit()
    db.refresh(att)

    return AttachmentRead(
        id=att.id,
        incident_id=att.incident_id,
        filename=att.filename,
        content_type=att.content_type,
        size_bytes=att.size_bytes,
        uploaded_by_id=att.uploaded_by_id,
        uploaded_by_name=user.name,
        uploaded_at=att.uploaded_at,
    )


@router.get("/{incident_id}/attachments", response_model=list[AttachmentRead])
def list_attachments(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    inc = get_incident_or_404(db, user, incident_id)
    attachments = db.scalars(
        select(Attachment)
        .where(Attachment.incident_id == inc.id)
        .options(joinedload(Attachment.uploaded_by))
        .order_by(Attachment.uploaded_at.desc())
    ).all()

    return [
        AttachmentRead(
            id=a.id,
            incident_id=a.incident_id,
            filename=a.filename,
            content_type=a.content_type,
            size_bytes=a.size_bytes,
            uploaded_by_id=a.uploaded_by_id,
            uploaded_by_name=a.uploaded_by.name if a.uploaded_by else None,
            uploaded_at=a.uploaded_at,
        )
        for a in attachments
    ]


@router.get("/{incident_id}/attachments/{attachment_id}/download")
def download_attachment(
    incident_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    inc = get_incident_or_404(db, user, incident_id)
    att = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.incident_id == inc.id,
        )
    )
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found.")

    file_path = Path(settings.UPLOAD_DIR) / att.stored_path
    if not file_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment file is missing on server.")

    return FileResponse(
        path=file_path,
        filename=att.filename,
        media_type=att.content_type or "application/octet-stream",
    )


@router.delete("/{incident_id}/attachments/{attachment_id}")
def delete_attachment(
    incident_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    att = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.incident_id == inc.id,
        )
    )
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found.")

    file_path = Path(settings.UPLOAD_DIR) / att.stored_path
    if file_path.exists():
        try:
            os.remove(file_path)
        except OSError:
            pass

    log_action(
        db, user, "incident.attachment_deleted", "attachment", att.id,
        {"incident_id": inc.id, "filename": att.filename},
    )
    db.delete(att)
    db.commit()

    return {"message": "Attachment deleted successfully.", "id": attachment_id}


# --- NLP Analysis & Root Cause Review -------------------------------------------------------------


@router.post("/{incident_id}/analyze", response_model=NLPAnalysisRead)
def run_nlp_analysis(
    incident_id: int,
    payload: NLPAnalyzeRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    override_text = payload.override_text if payload else None
    analysis = analyze_report(db, inc, user, override_text=override_text)

    log_action(db, user, "incident.analyzed", "nlp_analysis", analysis.id, {"incident_id": inc.id})
    db.commit()
    db.refresh(analysis)
    db.refresh(inc)

    # Trigger risk alert if High or Critical
    check_incident_risk_alerts(db, inc)
    db.commit()

    # Fetch updated root causes
    causes = db.scalars(
        select(IncidentRootCause)
        .where(IncidentRootCause.incident_id == inc.id)
        .options(joinedload(IncidentRootCause.root_cause))
    ).all()

    root_cause_reads = [
        IncidentRootCauseRead(
            id=c.id,
            incident_id=c.incident_id,
            root_cause_id=c.root_cause_id,
            root_cause_code=c.root_cause.code if c.root_cause else None,
            root_cause_name=c.root_cause.name if c.root_cause else None,
            source=c.source,
            confidence=c.confidence,
            evidence=c.evidence,
            review_status=c.review_status,
            reviewed_by_id=c.reviewed_by_id,
            analysis_id=c.analysis_id,
            created_at=c.created_at,
        )
        for c in causes
    ]

    return NLPAnalysisRead(
        id=analysis.id,
        incident_id=analysis.incident_id,
        model_version=analysis.model_version,
        result=analysis.result,
        risk_level=analysis.risk_level,
        risk_confidence=analysis.risk_confidence,
        created_by_id=analysis.created_by_id,
        created_at=analysis.created_at,
        root_causes=root_cause_reads,
    )


@router.post("/analyze-text", response_model=AnalyzeTextResponse)
def analyze_text_endpoint(
    payload: AnalyzeTextRequest,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    """Analyze arbitrary incident text without modifying database records."""
    return analyze_raw_text(
        db=db,
        text=payload.text,
        title=payload.title,
        incident_type=payload.incident_type,
        severity=payload.severity,
        injuries=payload.injuries,
    )


@router.get("/{incident_id}/root-causes", response_model=list[IncidentRootCauseRead])
def list_incident_root_causes(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Reader,
):
    inc = get_incident_or_404(db, user, incident_id)
    causes = db.scalars(
        select(IncidentRootCause)
        .where(IncidentRootCause.incident_id == inc.id)
        .options(joinedload(IncidentRootCause.root_cause))
        .order_by(IncidentRootCause.id.asc())
    ).all()

    return [
        IncidentRootCauseRead(
            id=c.id,
            incident_id=c.incident_id,
            root_cause_id=c.root_cause_id,
            root_cause_code=c.root_cause.code if c.root_cause else None,
            root_cause_name=c.root_cause.name if c.root_cause else None,
            source=c.source,
            confidence=c.confidence,
            evidence=c.evidence,
            review_status=c.review_status,
            reviewed_by_id=c.reviewed_by_id,
            analysis_id=c.analysis_id,
            created_at=c.created_at,
        )
        for c in causes
    ]


@router.post("/{incident_id}/root-causes", response_model=list[IncidentRootCauseRead])
def review_root_causes(
    incident_id: int,
    action_req: RootCauseReviewAction,
    db: Session = Depends(get_db),
    user: User = Writer,
):
    inc = get_incident_or_404(db, user, incident_id)
    check_incident_write_permission(user, inc.plant_id)

    if action_req.action in ("accept", "reject", "edit"):
        if not action_req.incident_root_cause_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "incident_root_cause_id is required for this action.",
            )
        irc = db.get(IncidentRootCause, action_req.incident_root_cause_id)
        if not irc or irc.incident_id != inc.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident root cause record not found.")

        if action_req.action == "accept":
            irc.review_status = ReviewStatus.ACCEPTED
            irc.reviewed_by_id = user.id
        elif action_req.action == "reject":
            irc.review_status = ReviewStatus.REJECTED
            irc.reviewed_by_id = user.id
        elif action_req.action == "edit":
            if action_req.root_cause_id:
                target_rc = db.get(RootCause, action_req.root_cause_id)
                if not target_rc:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "Target root cause category not found.")
                irc.root_cause_id = target_rc.id
            if action_req.evidence is not None:
                irc.evidence = action_req.evidence
            irc.review_status = ReviewStatus.EDITED
            irc.reviewed_by_id = user.id

    elif action_req.action == "add":
        if not action_req.root_cause_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "root_cause_id is required to add a manual root cause.",
            )
        rc = db.get(RootCause, action_req.root_cause_id)
        if not rc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Root cause category not found.")

        # Check existing manual cause
        existing = db.scalar(
            select(IncidentRootCause).where(
                IncidentRootCause.incident_id == inc.id,
                IncidentRootCause.root_cause_id == rc.id,
                IncidentRootCause.source == CauseSource.MANUAL,
            )
        )
        if existing:
            existing.evidence = action_req.evidence or existing.evidence
            existing.review_status = ReviewStatus.ACCEPTED
            existing.reviewed_by_id = user.id
        else:
            db.add(IncidentRootCause(
                incident_id=inc.id,
                root_cause_id=rc.id,
                source=CauseSource.MANUAL,
                confidence=action_req.confidence or 1.0,
                evidence=action_req.evidence,
                review_status=ReviewStatus.ACCEPTED,
                reviewed_by_id=user.id,
            ))

    # Advance workflow status if causes are identified
    if action_req.action in ("accept", "edit", "add"):
        if inc.status in (WorkflowStatus.REPORTED, WorkflowStatus.UNDER_INVESTIGATION):
            inc.status = WorkflowStatus.ROOT_CAUSE_IDENTIFIED

    log_action(
        db, user, f"incident.root_cause.{action_req.action}", "incident", inc.id,
        {"action": action_req.action},
    )
    db.commit()
    db.refresh(inc)

    return list_incident_root_causes(incident_id=inc.id, db=db, user=user)
