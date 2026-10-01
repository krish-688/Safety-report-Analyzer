"""Pydantic schemas for the Executive & Operational HSE Dashboard."""
from pydantic import BaseModel, ConfigDict


class DashboardSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_incidents: int
    open_incidents: int
    closed_incidents: int
    critical_risk: int
    high_risk: int
    medium_risk: int
    low_risk: int
    unanalyzed_risk: int
    total_injuries: int
    root_causes_identified: int


class MonthlyTrendItem(BaseModel):
    month: str
    total: int
    low: int
    medium: int
    high: int
    critical: int


class RootCauseParetoItem(BaseModel):
    category: str
    count: int
    percentage: float
    cumulative_percentage: float


class EquipmentWatchItem(BaseModel):
    equipment_id: int
    tag: str
    name: str
    equipment_type: str
    plant_name: str
    incident_count: int
    threshold_exceeded: bool


class PlantDistributionItem(BaseModel):
    plant_id: int
    plant_name: str
    plant_code: str
    total: int
    critical: int
    high: int
    medium: int
    low: int
