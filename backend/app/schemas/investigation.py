"""Pydantic schemas for Investigations and Corrective & Preventive Actions (CAPA)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActionStatus, ActionType


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incident_id: int
    investigator_id: int | None = None
    investigator_name: str | None = None
    assigned_by_id: int | None = None
    assigned_by_name: str | None = None
    due_date: date | None = None
    evidence: str | None = None
    findings: str | None = None
    verified_by_id: int | None = None
    verified_by_name: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InvestigationCreate(BaseModel):
    investigator_id: int | None = None
    due_date: date | None = None
    evidence: str | None = None
    findings: str | None = None


class InvestigationUpdate(BaseModel):
    investigator_id: int | None = None
    due_date: date | None = None
    evidence: str | None = None
    findings: str | None = None


class CorrectiveActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incident_id: int
    incident_reference: str | None = None
    plant_id: int | None = None
    plant_name: str | None = None
    investigation_id: int | None = None
    action_type: ActionType
    description: str
    owner_id: int | None = None
    owner_name: str | None = None
    equipment_id: int | None = None
    equipment_tag: str | None = None
    due_date: date
    status: ActionStatus
    approved_by_id: int | None = None
    approved_by_name: str | None = None
    completed_at: datetime | None = None
    created_at: datetime


class CorrectiveActionCreate(BaseModel):
    action_type: ActionType = ActionType.CORRECTIVE
    description: str = Field(..., min_length=5)
    owner_id: int | None = None
    equipment_id: int | None = None
    due_date: date


class CorrectiveActionUpdate(BaseModel):
    status: ActionStatus | None = None
    description: str | None = None
    owner_id: int | None = None
    due_date: date | None = None


class ActionApproval(BaseModel):
    approved: bool
    comments: str | None = None
