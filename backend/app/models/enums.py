import enum


class UserRole(str, enum.Enum):
    SAFETY_MANAGER = "Safety Manager"
    PLANT_MANAGER = "Plant Manager"
    SAFETY_OFFICER = "Safety Officer"
    ADMIN = "Admin"
    MANAGEMENT = "Management"


class UserStatus(str, enum.Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    REJECTED = "Rejected"
    INACTIVE = "Inactive"


class Severity(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkflowStatus(str, enum.Enum):
    """Investigation workflow; stored on Incident.status and shown as the stepper."""
    REPORTED = "Reported"
    UNDER_INVESTIGATION = "Under Investigation"
    ROOT_CAUSE_IDENTIFIED = "Root Cause Identified"
    ACTION_PENDING = "Action Pending"
    VERIFICATION = "Verification"
    CLOSED = "Closed"


class CauseSource(str, enum.Enum):
    NLP = "NLP"
    MANUAL = "Manual"


class ReviewStatus(str, enum.Enum):
    SUGGESTED = "Suggested"
    ACCEPTED = "Accepted"
    EDITED = "Edited"
    REJECTED = "Rejected"


class ActionType(str, enum.Enum):
    CORRECTIVE = "Corrective"
    PREVENTIVE = "Preventive"
    MAINTENANCE = "Maintenance"


class ActionStatus(str, enum.Enum):
    PROPOSED = "Proposed"          # waiting for Plant Manager approval
    APPROVED = "Approved"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    REJECTED = "Rejected"


class AlertType(str, enum.Enum):
    HIGH_RISK_INCIDENT = "High Risk Incident"
    CRITICAL_INCIDENT = "Critical Incident"
    INVESTIGATION_OVERDUE = "Investigation Overdue"
    ACTION_OVERDUE = "Action Overdue"
    EQUIPMENT_THRESHOLD = "Equipment Threshold"
    RECURRING_CAUSE = "Recurring Root Cause"
