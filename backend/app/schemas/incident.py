from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CauseSource, ReviewStatus, RiskLevel, Severity, WorkflowStatus


class IncidentEquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipment_id: int
    tag: str
    name: str
    equipment_type: str


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tag: str
    name: str
    equipment_type: str
    plant_id: int
    is_active: bool


class EquipmentCreate(BaseModel):
    plant_id: int
    tag: str = Field(..., min_length=2, max_length=40)
    name: str = Field(..., min_length=2, max_length=160)
    equipment_type: str = Field(..., min_length=2, max_length=80)
    is_active: bool = True


class EquipmentUpdate(BaseModel):
    tag: str | None = Field(default=None, min_length=2, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    equipment_type: str | None = Field(default=None, min_length=2, max_length=80)
    plant_id: int | None = None
    is_active: bool | None = None



class IncidentRootCauseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incident_id: int
    root_cause_id: int
    root_cause_code: str | None = None
    root_cause_name: str | None = None
    source: CauseSource
    confidence: float | None = None
    evidence: str | None = None
    review_status: ReviewStatus
    reviewed_by_id: int | None = None
    analysis_id: int | None = None
    created_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incident_id: int
    filename: str
    content_type: str | None = None
    size_bytes: int
    uploaded_by_id: int
    uploaded_by_name: str | None = None
    uploaded_at: datetime


class IncidentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    title: str
    occurred_at: datetime
    plant_id: int
    plant_name: str | None = None
    incident_type: str
    severity: Severity
    risk_level: RiskLevel | None = None
    risk_confidence: float | None = None
    status: WorkflowStatus
    injuries: int = 0
    created_at: datetime | None = None


class IncidentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    title: str
    occurred_at: datetime
    plant_id: int
    plant_name: str | None = None
    incident_type: str
    description: str
    severity: Severity
    injuries: int = 0
    damage_details: str | None = None
    immediate_actions: str | None = None
    risk_level: RiskLevel | None = None
    risk_confidence: float | None = None
    status: WorkflowStatus
    created_by_id: int
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    equipment: list[IncidentEquipmentRead] = Field(default_factory=list)
    root_causes: list[IncidentRootCauseRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    occurred_at: datetime
    plant_id: int | None = None  # Safety Manager can set any plant; Safety Officer defaults to own plant
    incident_type: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=10)
    severity: Severity = Severity.MEDIUM
    injuries: int = Field(0, ge=0)
    damage_details: str | None = None
    immediate_actions: str | None = None
    equipment_ids: list[int] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    occurred_at: datetime | None = None
    incident_type: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = Field(None, min_length=10)
    severity: Severity | None = None
    injuries: int | None = Field(None, ge=0)
    damage_details: str | None = None
    immediate_actions: str | None = None
    equipment_ids: list[int] | None = None
    status: WorkflowStatus | None = None


class NLPAnalyzeRequest(BaseModel):
    override_text: str | None = None


class NLPAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incident_id: int
    model_version: str
    result: dict
    risk_level: RiskLevel | None = None
    risk_confidence: float | None = None
    created_by_id: int | None = None
    created_at: datetime
    root_causes: list[IncidentRootCauseRead] = Field(default_factory=list)


class RootCauseReviewAction(BaseModel):
    action: Literal["accept", "edit", "reject", "add"]
    incident_root_cause_id: int | None = None  # required for accept, edit, reject
    root_cause_id: int | None = None          # required for add; optional for edit
    evidence: str | None = None
    confidence: float | None = None


class AnalyzeTextRequest(BaseModel):
    title: str = ""
    text: str = Field(..., min_length=5)
    incident_type: str | None = None
    severity: Severity = Severity.MEDIUM
    injuries: int = 0


class AnalyzeTextResponse(BaseModel):
    risk_level: RiskLevel
    risk_confidence: float
    result: dict

