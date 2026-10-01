from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import enum_col, utcnow
from app.models.enums import CauseSource, ReviewStatus, RiskLevel, Severity, WorkflowStatus


class Incident(Base):
    __tablename__ = "incident"
    __table_args__ = (
        Index("ix_incident_plant_occurred", "plant_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True)        # e.g. INC-2026-0001
    title: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plant_unit.id"), index=True)
    incident_type: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(enum_col(Severity), index=True)
    injuries: Mapped[int] = mapped_column(Integer, default=0)
    damage_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    immediate_actions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Filled from the AI analysis (or manual confirmation).
    risk_level: Mapped[RiskLevel | None] = mapped_column(enum_col(RiskLevel), nullable=True, index=True)
    risk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[WorkflowStatus] = mapped_column(
        enum_col(WorkflowStatus), default=WorkflowStatus.REPORTED, index=True
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    plant = relationship("PlantUnit")
    created_by = relationship("User", foreign_keys=[created_by_id])
    equipment_links = relationship("IncidentEquipment", cascade="all, delete-orphan", back_populates="incident")
    root_causes = relationship("IncidentRootCause", cascade="all, delete-orphan", back_populates="incident")
    attachments = relationship("Attachment", cascade="all, delete-orphan", back_populates="incident")
    nlp_analyses = relationship("NLPAnalysis", cascade="all, delete-orphan", back_populates="incident")
    investigation = relationship("Investigation", uselist=False, cascade="all, delete-orphan", back_populates="incident")


class IncidentEquipment(Base):
    __tablename__ = "incident_equipment"

    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), primary_key=True, index=True)

    incident = relationship("Incident", back_populates="equipment_links")
    equipment = relationship("Equipment")


class IncidentRootCause(Base):
    __tablename__ = "incident_root_cause"
    __table_args__ = (
        UniqueConstraint("incident_id", "root_cause_id", "source", name="uq_incident_cause_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), index=True)
    root_cause_id: Mapped[int] = mapped_column(ForeignKey("root_cause.id"), index=True)
    source: Mapped[CauseSource] = mapped_column(enum_col(CauseSource))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)    # None for Manual
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)         # evidence sentence
    review_status: Mapped[ReviewStatus] = mapped_column(enum_col(ReviewStatus), default=ReviewStatus.SUGGESTED)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("nlp_analysis.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    incident = relationship("Incident", back_populates="root_causes")
    root_cause = relationship("RootCause")
