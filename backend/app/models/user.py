from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import enum_col, utcnow
from app.models.enums import UserRole, UserStatus


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[UserRole] = mapped_column(enum_col(UserRole))               # final, admin-assigned
    requested_role: Mapped[UserRole | None] = mapped_column(enum_col(UserRole), nullable=True)
    status: Mapped[UserStatus] = mapped_column(enum_col(UserStatus), default=UserStatus.PENDING, index=True)

    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plant_unit.id"), nullable=True, index=True)
    preferred_plant_id: Mapped[int | None] = mapped_column(ForeignKey("plant_unit.id"), nullable=True)

    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    plant = relationship("PlantUnit", foreign_keys=[plant_id])
    preferred_plant = relationship("PlantUnit", foreign_keys=[preferred_plant_id])
