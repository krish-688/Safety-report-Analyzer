"""Admin-only user management."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models import PlantUnit, User
from app.models.enums import UserRole, UserStatus
from app.schemas.common import Message, Page
from app.schemas.user import PLANT_BOUND_ROLES, ApproveIn, ResetPasswordIn, UserOut, UserUpdateIn
from app.services.audit_service import log_action

router = APIRouter(prefix="/users", tags=["users (admin)"])
AdminOnly = Depends(require_roles(UserRole.ADMIN))


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


def _check_role_plant(db: Session, role: UserRole, plant_id: int | None) -> int | None:
    """Plant-bound roles need a plant; other roles are plant-independent (plant cleared)."""
    if role in PLANT_BOUND_ROLES:
        if plant_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{role.value} must be assigned a plant/unit.")
        if db.get(PlantUnit, plant_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Plant/unit does not exist.")
        return plant_id
    return None


def _other_active_admins(db: Session, exclude_id: int) -> int:
    return db.scalar(select(func.count(User.id)).where(
        User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE, User.id != exclude_id)) or 0


def _protect_last_admin(db: Session, target: User) -> None:
    if target.role == UserRole.ADMIN and target.status == UserStatus.ACTIVE and _other_active_admins(db, target.id) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove the last active Admin.")


@router.get("", response_model=Page[UserOut])
def list_users(
    status_: UserStatus | None = Query(None, alias="status"),
    role: UserRole | None = None,
    plant_id: int | None = None,
    q: str | None = Query(None, description="Search name or email"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = AdminOnly,
):
    stmt = select(User)
    if status_:
        stmt = stmt.where(User.status == status_)
    if role:
        stmt = stmt.where(User.role == role)
    if plant_id:
        stmt = stmt.where(User.plant_id == plant_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.name).like(like), func.lower(User.email).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * size).limit(size)).all()
    return Page[UserOut](items=items, total=total, page=page, size=size)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = AdminOnly):
    return _get_user(db, user_id)


@router.post("/{user_id}/approve", response_model=UserOut)
def approve_user(user_id: int, payload: ApproveIn, db: Session = Depends(get_db), admin: User = AdminOnly):
    user = _get_user(db, user_id)
    if user.status not in (UserStatus.PENDING, UserStatus.REJECTED):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only Pending or Rejected accounts can be approved.")
    user.plant_id = _check_role_plant(db, payload.role, payload.plant_id)
    user.role = payload.role
    user.status = UserStatus.ACTIVE
    user.approved_by_id = admin.id
    log_action(db, admin, "user.approved", "user", user.id,
               {"role": payload.role.value, "plant_id": user.plant_id})
    db.commit()
    return user


@router.post("/{user_id}/reject", response_model=UserOut)
def reject_user(user_id: int, db: Session = Depends(get_db), admin: User = AdminOnly):
    user = _get_user(db, user_id)
    if user.status != UserStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only Pending accounts can be rejected.")
    user.status = UserStatus.REJECTED
    log_action(db, admin, "user.rejected", "user", user.id)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdateIn, db: Session = Depends(get_db), admin: User = AdminOnly):
    user = _get_user(db, user_id)
    new_role = payload.role or user.role
    if new_role != user.role:
        _protect_last_admin(db, user)
    fields = payload.model_dump(exclude_unset=True)
    new_plant = payload.plant_id if "plant_id" in fields else user.plant_id
    before = {"name": user.name, "role": user.role.value, "plant_id": user.plant_id}
    user.plant_id = _check_role_plant(db, new_role, new_plant)
    user.role = new_role
    if payload.name:
        user.name = payload.name.strip()
    log_action(db, admin, "user.updated", "user", user.id,
               {"before": before, "after": {"name": user.name, "role": user.role.value, "plant_id": user.plant_id}})
    db.commit()
    return user


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), admin: User = AdminOnly):
    user = _get_user(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only Active accounts can be deactivated.")
    _protect_last_admin(db, user)
    user.status = UserStatus.INACTIVE
    log_action(db, admin, "user.deactivated", "user", user.id)
    db.commit()
    return user


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db), admin: User = AdminOnly):
    user = _get_user(db, user_id)
    if user.status != UserStatus.INACTIVE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only Inactive accounts can be re-activated.")
    user.status = UserStatus.ACTIVE
    log_action(db, admin, "user.activated", "user", user.id)
    db.commit()
    return user


@router.post("/{user_id}/reset-password", response_model=Message)
def reset_password(user_id: int, payload: ResetPasswordIn, db: Session = Depends(get_db), admin: User = AdminOnly):
    """Admin sets a new password and clears any lockout."""
    user = _get_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    user.failed_attempts = 0
    user.locked_until = None
    log_action(db, admin, "user.password_reset", "user", user.id)
    db.commit()
    return Message(message=f"Password reset for {user.email}.")
