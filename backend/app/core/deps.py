"""Reusable FastAPI dependencies: current user and role checks."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole, UserStatus

bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token from POST /auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise _unauthorized("Not authenticated. Please log in.")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session has expired. Please log in again.")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid authentication token.")

    user = db.get(User, int(payload["sub"]))
    # Role/status are always read from the DB, so admin changes apply immediately.
    if user is None or user.status != UserStatus.ACTIVE:
        raise _unauthorized("Account is not active.")
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: `Depends(require_roles(UserRole.ADMIN))` -> returns the user or 403."""
    allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({user.role.value}) is not allowed to perform this action.",
            )
        return user

    return checker
