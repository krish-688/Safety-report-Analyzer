"""Plants & Units Management Router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Equipment, PlantUnit, User
from app.models.enums import UserRole
from app.schemas.incident import EquipmentCreate, EquipmentOut
from app.schemas.user import PlantCreate, PlantOut, PlantUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/plants", tags=["plants"])
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get("", response_model=list[PlantOut])
def list_plants(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Any logged-in user can list active plants."""
    return db.scalars(select(PlantUnit).where(PlantUnit.is_active).order_by(PlantUnit.name)).all()


@router.get("/all", response_model=list[PlantOut])
def list_all_plants(db: Session = Depends(get_db), _: User = AdminOnly):
    """Admin-only list of all plants, including inactive ones."""
    return db.scalars(select(PlantUnit).order_by(PlantUnit.id)).all()


@router.get("/{plant_id}", response_model=PlantOut)
def get_plant(plant_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    plant = db.get(PlantUnit, plant_id)
    if not plant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{plant_id} not found.")
    return plant


@router.post("", response_model=PlantOut, status_code=status.HTTP_201_CREATED)
def create_plant(payload: PlantCreate, db: Session = Depends(get_db), admin: User = AdminOnly):
    # Check code or name uniqueness
    existing_code = db.scalar(select(PlantUnit).where(PlantUnit.code == payload.code.strip().upper()))
    if existing_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Plant code '{payload.code}' already exists.")

    existing_name = db.scalar(select(PlantUnit).where(PlantUnit.name == payload.name.strip()))
    if existing_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Plant name '{payload.name}' already exists.")

    plant = PlantUnit(
        name=payload.name.strip(),
        code=payload.code.strip().upper(),
        location=payload.location.strip() if payload.location else None,
        is_active=payload.is_active,
    )
    db.add(plant)
    db.flush()

    log_action(db, admin, "plant.created", "plant_unit", plant.id, {"code": plant.code, "name": plant.name})
    db.commit()
    db.refresh(plant)
    return plant


@router.patch("/{plant_id}", response_model=PlantOut)
def update_plant(plant_id: int, payload: PlantUpdate, db: Session = Depends(get_db), admin: User = AdminOnly):
    plant = db.get(PlantUnit, plant_id)
    if not plant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{plant_id} not found.")

    if payload.name is not None:
        name_strip = payload.name.strip()
        existing_name = db.scalar(select(PlantUnit).where(PlantUnit.name == name_strip, PlantUnit.id != plant_id))
        if existing_name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Plant name '{name_strip}' already in use.")
        plant.name = name_strip

    if payload.code is not None:
        code_strip = payload.code.strip().upper()
        existing_code = db.scalar(select(PlantUnit).where(PlantUnit.code == code_strip, PlantUnit.id != plant_id))
        if existing_code:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Plant code '{code_strip}' already in use.")
        plant.code = code_strip

    if payload.location is not None:
        plant.location = payload.location.strip() if payload.location else None

    if payload.is_active is not None:
        plant.is_active = payload.is_active

    log_action(db, admin, "plant.updated", "plant_unit", plant.id, {"name": plant.name, "is_active": plant.is_active})
    db.commit()
    db.refresh(plant)
    return plant


@router.get("/{plant_id}/equipment", response_model=list[EquipmentOut])
def list_plant_equipment(
    plant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all equipment associated with a specific plant."""
    plant = db.get(PlantUnit, plant_id)
    if not plant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{plant_id} not found.")

    return db.scalars(
        select(Equipment)
        .where(Equipment.plant_id == plant_id, Equipment.is_active == True)  # noqa: E712
        .order_by(Equipment.tag)
    ).all()


@router.post("/{plant_id}/equipment", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
def create_plant_equipment(
    plant_id: int,
    payload: EquipmentCreate,
    db: Session = Depends(get_db),
    admin: User = AdminOnly,
):
    plant = db.get(PlantUnit, plant_id)
    if not plant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Plant #{plant_id} not found.")

    tag_clean = payload.tag.strip().upper()
    existing_eq = db.scalar(select(Equipment).where(Equipment.tag == tag_clean))
    if existing_eq:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Equipment tag '{tag_clean}' already exists.")

    eq = Equipment(
        plant_id=plant_id,
        tag=tag_clean,
        name=payload.name.strip(),
        equipment_type=payload.equipment_type.strip(),
        is_active=payload.is_active,
    )
    db.add(eq)
    db.flush()

    log_action(db, admin, "equipment.created", "equipment", eq.id, {"tag": eq.tag, "plant_id": plant_id})
    db.commit()
    db.refresh(eq)
    return eq
