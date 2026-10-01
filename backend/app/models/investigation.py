from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import enum_col, utcnow
from app.models.enums import ActionStatus, ActionType


class Investigation(Base):
    """One investigation per incident. The workflow status lives on Incident.status."""
    __tablename__ = "investigation"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), unique=True)
    investigator_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    incident = relationship("Incident", back_populates="investigation")
    investigator = relationship("User", foreign_keys=[investigator_id])


class CorrectiveAction(Base):
    __tablename__ = "corrective_action"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), index=True)
    investigation_id: Mapped[int | None] = mapped_column(ForeignKey("investigation.id"), nullable=True)
    action_type: Mapped[ActionType] = mapped_column(enum_col(ActionType))
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[ActionStatus] = mapped_column(enum_col(ActionStatus), default=ActionStatus.PROPOSED, index=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    incident = relationship("Incident")
    owner = relationship("User", foreign_keys=[owner_id])
    equipment = relationship("Equipment")
