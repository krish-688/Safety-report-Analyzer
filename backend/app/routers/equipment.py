"""Equipment Router for listing and administrator updates."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Equipment, PlantUnit, User
from app.models.enums import UserRole
from app.schemas.incident import EquipmentOut, EquipmentUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/equipment", tags=["equipment"])
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get("", response_model=list[EquipmentOut])
def list_equipment(
    plant_id: int | None = Query(None),
    equipment_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Equipment)
    if plant_id is not None:
        stmt = stmt.where(Equipment.plant_id == plant_id)
    if equipment_type is not None:
        stmt = stmt.where(Equipment.equipment_type == equipment_type)
    if is_active is not None:
        stmt = stmt.where(Equipment.is_active == is_active)
    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(or_(Equipment.tag.ilike(s), Equipment.name.ilike(s)))

    return db.scalars(stmt.order_by(Equipment.plant_id, Equipment.tag).limit(limit)).all()


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    eq = db.get(Equipment, equipment_id)
    if not eq:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment #{equipment_id} not found.")
    return eq


@router.patch("/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    equipment_id: int,
    payload: EquipmentUpdate,
    db: Session = Depends(get_db),
    admin: User = AdminOnly,
):
    eq = db.get(Equipment, equipment_id)
    if not eq:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment #{equipment_id} not found.")

    if payload.tag is not None:
        tag_clean = payload.tag.strip().upper()
        existing = db.scalar(select(Equipment).where(Equipment.tag == tag_clean, Equipment.id != equipment_id))
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tag '{tag_clean}' already in use.")
        eq.tag = tag_clean

    if payload.name is not None:
        eq.name = payload.name.strip()

    if payload.equipment_type is not None:
        eq.equipment_type = payload.equipment_type.strip()

    if payload.plant_id is not None:
        plant = db.get(PlantUnit, payload.plant_id)
        if not plant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{payload.plant_id} not found.")
        eq.plant_id = payload.plant_id

    if payload.is_active is not None:
        eq.is_active = payload.is_active

    log_action(db, admin, "equipment.updated", "equipment", eq.id, {"tag": eq.tag, "is_active": eq.is_active})
    db.commit()
    db.refresh(eq)
    return eq
