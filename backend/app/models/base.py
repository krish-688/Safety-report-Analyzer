from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum


def utcnow() -> datetime:
    """Naive UTC timestamp (portable across SQLite/PostgreSQL/MySQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enum_col(enum_cls: type[PyEnum], length: int = 32) -> SAEnum:
    """Store enums as VARCHAR of the human-readable value (no native DB enum types)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
