"""Audit Log Router for Administrative Compliance."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models import AuditLog, User
from app.models.enums import UserRole
from app.schemas.user import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit (admin)"])
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    user_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = AdminOnly,
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action.strip()}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)

    return db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)).all()
