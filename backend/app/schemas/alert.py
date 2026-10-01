"""Pydantic schemas for Alerts and Notifications."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertType


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    alert_type: AlertType
    title: str
    message: str
    incident_id: int | None = None
    incident_reference: str | None = None
    equipment_id: int | None = None
    equipment_tag: str | None = None
    is_read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread_count: int


class ThresholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    value: int
    description: str | None = None


class ThresholdUpdate(BaseModel):
    value: int
