from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_action(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    """Add an audit row to the current transaction (caller commits)."""
    db.add(AuditLog(
        user_id=actor.id if actor else None,
        action=action, entity_type=entity_type, entity_id=entity_id, details=details,
    ))
