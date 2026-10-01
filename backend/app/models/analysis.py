from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import enum_col, utcnow
from app.models.enums import RiskLevel


class NLPAnalysis(Base):
    """One run of analyze_report(). `result` stores the full JSON returned by the pipeline."""
    __tablename__ = "nlp_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachment.id"), nullable=True)
    model_version: Mapped[str] = mapped_column(String(60), default="stub-0.1")
    result: Mapped[dict] = mapped_column(JSON)
    risk_level: Mapped[RiskLevel | None] = mapped_column(enum_col(RiskLevel), nullable=True)
    risk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    incident = relationship("Incident", back_populates="nlp_analyses")
    created_by = relationship("User")

