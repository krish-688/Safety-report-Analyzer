"""Alerts & Notifications Engine.

Evaluates safety thresholds, overdue investigations, high/critical risk events,
recurring root causes, and equipment repeat failure warnings.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Alert, AlertThreshold, CorrectiveAction, Equipment, Incident, IncidentEquipment,
    IncidentRootCause, Investigation, User,
)
from app.models.enums import ActionStatus, AlertType, RiskLevel, UserRole, WorkflowStatus


def _get_threshold(db: Session, key: str, default: int) -> int:
    val = db.scalar(select(AlertThreshold.value).where(AlertThreshold.key == key))
    return val if val is not None else default


def notify_users_for_incident(
    db: Session,
    incident: Incident,
    alert_type: AlertType,
    title: str,
    message: str,
    equipment_id: int | None = None,
) -> list[Alert]:
    """Notify relevant safety leadership for an incident (Safety Manager + assigned Plant Manager)."""
    # 1. Safety Managers (all plants)
    safety_managers = db.scalars(
        select(User).where(User.role == UserRole.SAFETY_MANAGER, User.status == "Active")
    ).all()

    # 2. Plant Manager for the incident's plant
    plant_managers = db.scalars(
        select(User).where(
            User.role == UserRole.PLANT_MANAGER,
            User.plant_id == incident.plant_id,
            User.status == "Active",
        )
    ).all()

    recipients = set(safety_managers + plant_managers)
    created_alerts = []
    for user in recipients:
        # Avoid duplicate unread alerts for same user and incident
        existing = db.scalar(
            select(Alert).where(
                Alert.user_id == user.id,
                Alert.incident_id == incident.id,
                Alert.alert_type == alert_type,
                Alert.is_read == False,  # noqa: E712
            )
        )
        if not existing:
            alert = Alert(
                user_id=user.id,
                alert_type=alert_type,
                title=title,
                message=message,
                incident_id=incident.id,
                equipment_id=equipment_id,
            )
            db.add(alert)
            created_alerts.append(alert)

    db.flush()
    return created_alerts


def check_incident_risk_alerts(db: Session, incident: Incident) -> None:
    """Trigger notifications if incident has high or critical risk."""
    if incident.risk_level == RiskLevel.CRITICAL:
        notify_users_for_incident(
            db=db,
            incident=incident,
            alert_type=AlertType.CRITICAL_INCIDENT,
            title=f"🚨 CRITICAL Incident: {incident.reference}",
            message=f"Critical risk incident '{incident.title}' was recorded at Plant #{incident.plant_id}.",
        )
    elif incident.risk_level == RiskLevel.HIGH:
        notify_users_for_incident(
            db=db,
            incident=incident,
            alert_type=AlertType.HIGH_RISK_INCIDENT,
            title=f"⚠️ High Risk Incident: {incident.reference}",
            message=f"High risk safety incident '{incident.title}' reported. Immediate investigation recommended.",
        )


def check_equipment_incident_thresholds(db: Session, incident: Incident) -> None:
    """Check if any equipment linked to this incident exceeds the repeat failure threshold."""
    eq_threshold = _get_threshold(db, "equipment_incident_count", 3)
    window_months = _get_threshold(db, "equipment_window_months", 12)
    cutoff = datetime.utcnow() - timedelta(days=window_months * 30)

    for link in incident.equipment_links:
        eq_id = link.equipment_id
        eq = link.equipment or db.get(Equipment, eq_id)

        count = db.scalar(
            select(func.count(IncidentEquipment.incident_id))
            .join(Incident, Incident.id == IncidentEquipment.incident_id)
            .where(
                IncidentEquipment.equipment_id == eq_id,
                Incident.occurred_at >= cutoff,
            )
        ) or 0

        if count >= eq_threshold:
            eq_tag = eq.tag if eq else f"#{eq_id}"
            notify_users_for_incident(
                db=db,
                incident=incident,
                alert_type=AlertType.EQUIPMENT_THRESHOLD,
                title=f"⚙️ Repeat Equipment Alert: {eq_tag}",
                message=f"Equipment {eq_tag} has experienced {count} safety incidents within {window_months} months (Threshold: {eq_threshold}). Maintenance review required.",
                equipment_id=eq_id,
            )


def scan_for_overdue_items(db: Session) -> int:
    """Scan database for overdue investigations and corrective actions; generate alerts."""
    today = date.today()
    created_count = 0

    # 1. Overdue Investigations
    overdue_invs = db.scalars(
        select(Investigation)
        .join(Incident, Incident.id == Investigation.incident_id)
        .where(
            Investigation.due_date < today,
            Investigation.closed_at == None,  # noqa: E711
            Incident.status != WorkflowStatus.CLOSED,
        )
    ).all()

    for inv in overdue_invs:
        inc = inv.incident
        if inv.investigator_id:
            inv_user = inv.investigator or db.get(User, inv.investigator_id)
            if inv_user:
                existing = db.scalar(
                    select(Alert).where(
                        Alert.user_id == inv_user.id,
                        Alert.incident_id == inc.id,
                        Alert.alert_type == AlertType.INVESTIGATION_OVERDUE,
                        Alert.is_read == False,  # noqa: E712
                    )
                )
                if not existing:
                    db.add(Alert(
                        user_id=inv_user.id,
                        alert_type=AlertType.INVESTIGATION_OVERDUE,
                        title=f"⏰ Investigation Overdue: {inc.reference}",
                        message=f"Investigation for incident {inc.reference} was due on {inv.due_date} and remains open.",
                        incident_id=inc.id,
                    ))
                    created_count += 1

    # 2. Overdue Corrective Actions
    overdue_actions = db.scalars(
        select(CorrectiveAction)
        .join(Incident, Incident.id == CorrectiveAction.incident_id)
        .where(
            CorrectiveAction.due_date < today,
            CorrectiveAction.status != ActionStatus.COMPLETED,
            CorrectiveAction.status != ActionStatus.REJECTED,
        )
    ).all()

    for act in overdue_actions:
        inc = act.incident
        target_users = set()
        if act.owner_id:
            target_users.add(act.owner_id)
        # Also notify plant manager
        pm = db.scalar(
            select(User.id).where(
                User.role == UserRole.PLANT_MANAGER,
                User.plant_id == inc.plant_id,
                User.status == "Active",
            )
        )
        if pm:
            target_users.add(pm)

        for uid in target_users:
            existing = db.scalar(
                select(Alert).where(
                    Alert.user_id == uid,
                    Alert.incident_id == inc.id,
                    Alert.alert_type == AlertType.ACTION_OVERDUE,
                    Alert.is_read == False,  # noqa: E712
                )
            )
            if not existing:
                db.add(Alert(
                    user_id=uid,
                    alert_type=AlertType.ACTION_OVERDUE,
                    title=f"⏰ Action Overdue: {act.description[:40]}...",
                    message=f"Action '{act.description}' for incident {inc.reference} is overdue (target: {act.due_date}).",
                    incident_id=inc.id,
                    equipment_id=act.equipment_id,
                ))
                created_count += 1

    db.commit()
    return created_count
