from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import utcnow


class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))            # original name
    stored_path: Mapped[str] = mapped_column(String(500))         # path relative to UPLOAD_DIR
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    incident = relationship("Incident", back_populates="attachments")
    uploaded_by = relationship("User")

