from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.user import PlantOut, UserOut, validate_password_strength


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    requested_role: UserRole
    preferred_plant_id: int | None = None

    check_password = field_validator("password")(validate_password_strength)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("requested_role")
    @classmethod
    def _not_admin(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Admin accounts cannot be requested. Choose another role.")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RegisterOptions(BaseModel):
    roles: list[UserRole]
    plants: list[PlantOut]
