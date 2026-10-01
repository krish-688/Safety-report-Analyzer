import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import PlantUnit, User
from app.models.base import utcnow
from app.models.enums import UserRole, UserStatus
from app.schemas.auth import LoginIn, RegisterIn, RegisterOptions, TokenOut
from app.schemas.common import Message
from app.schemas.user import PLANT_BOUND_ROLES, UserOut
from datetime import timedelta
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

BLOCKED_MESSAGES = {
    UserStatus.PENDING: "Your account is pending approval by an administrator.",
    UserStatus.REJECTED: "Your registration was rejected. Please contact an administrator.",
    UserStatus.INACTIVE: "Your account has been deactivated. Please contact an administrator.",
}


@router.get("/register-options", response_model=RegisterOptions)
def register_options(db: Session = Depends(get_db)):
    """Public: roles and plants offered on the registration form (Admin is never offered)."""
    plants = db.scalars(select(PlantUnit).where(PlantUnit.is_active).order_by(PlantUnit.name)).all()
    return RegisterOptions(roles=[r for r in UserRole if r != UserRole.ADMIN], plants=plants)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    if payload.preferred_plant_id is not None:
        plant = db.get(PlantUnit, payload.preferred_plant_id)
        if plant is None or not plant.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Selected plant/unit does not exist.")
    elif payload.requested_role in PLANT_BOUND_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please choose your plant/unit.")

    user = User(
        name=payload.name.strip(), email=payload.email, password_hash=hash_password(payload.password),
        role=payload.requested_role,  # placeholder until an Admin approves; login is blocked while Pending
        requested_role=payload.requested_role, preferred_plant_id=payload.preferred_plant_id,
        status=UserStatus.PENDING,
    )
    db.add(user)
    db.flush()
    log_action(db, user, "user.registered", "user", user.id,
               {"requested_role": payload.requested_role.value, "preferred_plant_id": payload.preferred_plant_id})
    db.commit()
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    if user is None:
        raise invalid

    now = utcnow()
    if user.locked_until and user.locked_until > now:
        minutes = max(1, math.ceil((user.locked_until - now).total_seconds() / 60))
        raise HTTPException(status.HTTP_423_LOCKED,
                            f"Account locked after too many failed attempts. Try again in {minutes} minute(s).")

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.MAX_FAILED_ATTEMPTS:
            user.failed_attempts = 0
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            log_action(db, user, "auth.locked", "user", user.id, {"minutes": settings.LOCKOUT_MINUTES})
            db.commit()
            raise HTTPException(status.HTTP_423_LOCKED,
                                f"Too many failed attempts. Account locked for {settings.LOCKOUT_MINUTES} minutes.")
        log_action(db, user, "auth.login_failed", "user", user.id)
        db.commit()
        remaining = settings.MAX_FAILED_ATTEMPTS - user.failed_attempts
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            f"Invalid email or password. {remaining} attempt(s) left before the account is locked.")

    # Password is correct: now report account state (avoids leaking status to guessers).
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, BLOCKED_MESSAGES[user.status])

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    log_action(db, user, "auth.login", "user", user.id)
    db.commit()

    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenOut(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", response_model=Message)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tokens are stateless: the client discards the token. This only records the event."""
    log_action(db, user, "auth.logout", "user", user.id)
    db.commit()
    return Message(message="Logged out.")
