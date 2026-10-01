import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole, UserStatus

PLANT_BOUND_ROLES = {UserRole.PLANT_MANAGER, UserRole.SAFETY_OFFICER}


def validate_password_strength(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters with an uppercase letter, a lowercase letter and a number.")
    return v


class PlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    location: str | None = None
    is_active: bool = True


class PlantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    code: str = Field(..., min_length=2, max_length=20)
    location: str | None = None
    is_active: bool = True


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=20)
    location: str | None = None
    is_active: bool | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    details: dict | None = None
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: UserRole
    requested_role: UserRole | None = None
    status: UserStatus
    plant_id: int | None = None
    plant: PlantOut | None = None
    preferred_plant_id: int | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class ApproveIn(BaseModel):
    role: UserRole
    plant_id: int | None = None


class UserUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: UserRole | None = None
    plant_id: int | None = None


class ResetPasswordIn(BaseModel):
    new_password: str

    check_password = field_validator("new_password")(validate_password_strength)
