"""Alerts & Notifications Router."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Alert, AlertThreshold, Equipment, Incident, User
from app.models.enums import UserRole
from app.schemas.alert import AlertRead, ThresholdRead, ThresholdUpdate, UnreadCountResponse
from app.services.alert_service import scan_for_overdue_items

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_my_alerts(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Alert)
        .where(Alert.user_id == user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Alert.is_read == False)  # noqa: E712

    alerts = db.scalars(stmt).all()

    # Enrich with references and equipment tags
    results = []
    for a in alerts:
        inc_ref = None
        if a.incident_id:
            inc = db.get(Incident, a.incident_id)
            if inc:
                inc_ref = inc.reference
        eq_tag = None
        if a.equipment_id:
            eq = db.get(Equipment, a.equipment_id)
            if eq:
                eq_tag = eq.tag

        results.append(
            AlertRead(
                id=a.id,
                user_id=a.user_id,
                alert_type=a.alert_type,
                title=a.title,
                message=a.message,
                incident_id=a.incident_id,
                incident_reference=inc_ref,
                equipment_id=a.equipment_id,
                equipment_tag=eq_tag,
                is_read=a.is_read,
                created_at=a.created_at,
            )
        )
    return results


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = db.scalar(
        select(func.count(Alert.id)).where(Alert.user_id == user.id, Alert.is_read == False)  # noqa: E712
    ) or 0
    return UnreadCountResponse(unread_count=count)


@router.post("/{alert_id}/read", response_model=AlertRead)
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")

    alert.is_read = True
    db.commit()
    db.refresh(alert)

    inc = db.get(Incident, alert.incident_id) if alert.incident_id else None
    eq = db.get(Equipment, alert.equipment_id) if alert.equipment_id else None

    return AlertRead(
        id=alert.id,
        user_id=alert.user_id,
        alert_type=alert.alert_type,
        title=alert.title,
        message=alert.message,
        incident_id=alert.incident_id,
        incident_reference=inc.reference if inc else None,
        equipment_id=alert.equipment_id,
        equipment_tag=eq.tag if eq else None,
        is_read=alert.is_read,
        created_at=alert.created_at,
    )


@router.post("/mark-all-read")
def mark_all_alerts_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alerts = db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.is_read == False)).all()  # noqa: E712
    for a in alerts:
        a.is_read = True
    db.commit()
    return {"message": "All alerts marked as read.", "count": len(alerts)}


@router.post("/scan")
def trigger_overdue_scan(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    created = scan_for_overdue_items(db)
    return {"message": "Background scan completed.", "new_alerts_created": created}


@router.get("/thresholds", response_model=list[ThresholdRead])
def list_thresholds(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.scalars(select(AlertThreshold).order_by(AlertThreshold.id)).all()


@router.patch("/thresholds/{key}", response_model=ThresholdRead)
def update_threshold(
    key: str,
    payload: ThresholdUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SAFETY_MANAGER)),
):
    thresh = db.scalar(select(AlertThreshold).where(AlertThreshold.key == key))
    if not thresh:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Threshold '{key}' not found.")

    thresh.value = payload.value
    db.commit()
    db.refresh(thresh)
    return thresh
