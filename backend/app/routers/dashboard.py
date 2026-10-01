"""Dashboard router: high-performance aggregations, KPIs, trends, and Pareto breakdowns."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.db.session import get_db
from app.models import (
    AlertThreshold, Equipment, Incident, IncidentEquipment, IncidentRootCause, PlantUnit, RootCause, User,
)
from app.models.enums import RiskLevel, Severity, WorkflowStatus
from app.schemas.dashboard import (
    DashboardSummary, EquipmentWatchItem, MonthlyTrendItem, PlantDistributionItem, RootCauseParetoItem,
)
from app.services.incident_service import INCIDENT_READ_ROLES, scope_incident_query

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Reader = Depends(require_roles(*INCIDENT_READ_ROLES))


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    plant_id: int | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    stmt = scope_incident_query(user)
    if plant_id is not None:
        stmt = stmt.where(Incident.plant_id == plant_id)
    if from_date is not None:
        stmt = stmt.where(Incident.occurred_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Incident.occurred_at <= to_date)

    incidents = db.scalars(stmt).all()

    total = len(incidents)
    open_statuses = {
        WorkflowStatus.REPORTED,
        WorkflowStatus.UNDER_INVESTIGATION,
        WorkflowStatus.ACTION_PENDING,
    }
    identified_statuses = {
        WorkflowStatus.ROOT_CAUSE_IDENTIFIED,
        WorkflowStatus.ACTION_PENDING,
        WorkflowStatus.VERIFICATION,
        WorkflowStatus.CLOSED,
    }

    open_count = sum(1 for i in incidents if i.status in open_statuses)
    closed_count = sum(1 for i in incidents if i.status == WorkflowStatus.CLOSED)
    rc_identified = sum(1 for i in incidents if i.status in identified_statuses)

    critical_risk = sum(1 for i in incidents if i.risk_level == RiskLevel.CRITICAL)
    high_risk = sum(1 for i in incidents if i.risk_level == RiskLevel.HIGH)
    medium_risk = sum(1 for i in incidents if i.risk_level == RiskLevel.MEDIUM)
    low_risk = sum(1 for i in incidents if i.risk_level == RiskLevel.LOW)
    unanalyzed = sum(1 for i in incidents if i.risk_level is None)
    total_injuries = sum(i.injuries for i in incidents)

    return DashboardSummary(
        total_incidents=total,
        open_incidents=open_count,
        closed_incidents=closed_count,
        critical_risk=critical_risk,
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        unanalyzed_risk=unanalyzed,
        total_injuries=total_injuries,
        root_causes_identified=rc_identified,
    )


@router.get("/trends", response_model=list[MonthlyTrendItem])
def get_monthly_trends(
    plant_id: int | None = Query(None),
    months: int = Query(18, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    stmt = scope_incident_query(user)
    if plant_id is not None:
        stmt = stmt.where(Incident.plant_id == plant_id)

    incidents = db.scalars(stmt).all()

    # Aggregate by year-month
    monthly_data: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    )

    for inc in incidents:
        if not inc.occurred_at:
            continue
        ym = inc.occurred_at.strftime("%Y-%m")
        bucket = monthly_data[ym]
        bucket["total"] += 1
        if inc.risk_level == RiskLevel.CRITICAL:
            bucket["critical"] += 1
        elif inc.risk_level == RiskLevel.HIGH:
            bucket["high"] += 1
        elif inc.risk_level == RiskLevel.MEDIUM:
            bucket["medium"] += 1
        else:
            bucket["low"] += 1

    sorted_months = sorted(monthly_data.keys())[-months:]
    return [
        MonthlyTrendItem(
            month=m,
            total=monthly_data[m]["total"],
            low=monthly_data[m]["low"],
            medium=monthly_data[m]["medium"],
            high=monthly_data[m]["high"],
            critical=monthly_data[m]["critical"],
        )
        for m in sorted_months
    ]


@router.get("/pareto-causes", response_model=list[RootCauseParetoItem])
def get_root_cause_pareto(
    plant_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    # Fetch scoped incident IDs
    scoped_stmt = scope_incident_query(user, select(Incident.id))
    if plant_id is not None:
        scoped_stmt = scoped_stmt.where(Incident.plant_id == plant_id)

    # Join IncidentRootCause with RootCause
    query = (
        select(RootCause.name, func.count(IncidentRootCause.id).label("count"))
        .join(IncidentRootCause, IncidentRootCause.root_cause_id == RootCause.id)
        .where(IncidentRootCause.incident_id.in_(scoped_stmt))
        .group_by(RootCause.id, RootCause.name)
        .order_by(func.count(IncidentRootCause.id).desc())
    )
    rows = db.execute(query).all()

    total_occurrences = sum(count for _, count in rows) or 1
    pareto_items = []
    accumulated = 0.0

    for name, count in rows:
        pct = (count / total_occurrences) * 100
        accumulated += pct
        pareto_items.append(
            RootCauseParetoItem(
                category=name,
                count=count,
                percentage=round(pct, 1),
                cumulative_percentage=round(min(accumulated, 100.0), 1),
            )
        )

    return pareto_items


@router.get("/equipment-watch", response_model=list[EquipmentWatchItem])
def get_equipment_watchlist(
    plant_id: int | None = Query(None),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Reader,
):
    scoped_incidents = scope_incident_query(user, select(Incident.id))
    if plant_id is not None:
        scoped_incidents = scoped_incidents.where(Incident.plant_id == plant_id)

    # Threshold for recurrent incidents (default 3)
    thresh = db.scalar(
        select(AlertThreshold.value).where(AlertThreshold.key == "equipment_incident_count")
    )
    threshold_limit = thresh if thresh is not None else 3

    # Count incident occurrences per equipment item
    q = (
        select(
            Equipment.id,
            Equipment.tag,
            Equipment.name,
            Equipment.equipment_type,
            PlantUnit.name.label("plant_name"),
            func.count(IncidentEquipment.incident_id).label("incident_count"),
        )
        .join(IncidentEquipment, IncidentEquipment.equipment_id == Equipment.id)
        .join(PlantUnit, PlantUnit.id == Equipment.plant_id)
        .where(IncidentEquipment.incident_id.in_(scoped_incidents))
        .group_by(
            Equipment.id,
            Equipment.tag,
            Equipment.name,
            Equipment.equipment_type,
            PlantUnit.name,
        )
        .order_by(func.count(IncidentEquipment.incident_id).desc())
        .limit(limit)
    )
    rows = db.execute(q).all()

    return [
        EquipmentWatchItem(
            equipment_id=r.id,
            tag=r.tag,
            name=r.name,
            equipment_type=r.equipment_type,
            plant_name=r.plant_name,
            incident_count=r.incident_count,
            threshold_exceeded=r.incident_count >= threshold_limit,
        )
        for r in rows
    ]


@router.get("/plant-distribution", response_model=list[PlantDistributionItem])
def get_plant_distribution(
    db: Session = Depends(get_db),
    user: User = Reader,
):
    scoped_incidents = db.scalars(
        scope_incident_query(user).options(joinedload(Incident.plant))
    ).all()

    plants_data: dict[int, dict[str, Any]] = {}
    for inc in scoped_incidents:
        pid = inc.plant_id
        if pid not in plants_data:
            plants_data[pid] = {
                "plant_id": pid,
                "plant_name": inc.plant.name if inc.plant else f"Plant #{pid}",
                "plant_code": inc.plant.code if inc.plant else f"P{pid}",
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }
        p = plants_data[pid]
        p["total"] += 1
        if inc.risk_level == RiskLevel.CRITICAL:
            p["critical"] += 1
        elif inc.risk_level == RiskLevel.HIGH:
            p["high"] += 1
        elif inc.risk_level == RiskLevel.MEDIUM:
            p["medium"] += 1
        else:
            p["low"] += 1

    return [PlantDistributionItem(**p) for p in plants_data.values()]
