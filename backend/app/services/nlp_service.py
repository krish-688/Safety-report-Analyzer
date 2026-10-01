"""NLP Analysis Service Stub.

Provides realistic heuristic predictions for incident risk levels, root causes,
extracted entities, and evidence sentences. In later stages, this module can be
swapped with a full transformer or LLM pipeline without breaking API contracts.
"""
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentRootCause, NLPAnalysis, RootCause, User
from app.models.enums import CauseSource, ReviewStatus, RiskLevel, Severity

# Cues for Risk Level determination
CRITICAL_CUES = [
    "fatality", "death", "explosion", "toxic cloud", "runaway", "uncontrolled",
    "critical", "catastrophic", "blast", "major loss",
]
HIGH_CUES = [
    "fire", "hydrocarbon release", "rupture", "loss of containment", "emergency relief",
    "flare", "hospitalized", "severe", "evacuate", "flammable release", "burn",
]
MEDIUM_CUES = [
    "overpressure", "seal leak", "vibration", "alarm", "flange", "corrosion",
    "trip", "excursion", "spill", "leak", "worn", "bearing", "tripped",
]
LOW_CUES = [
    "near miss", "minor", "checklist", "inspection", "sampling", "procedural",
    "housekeeping", "observation", "slip",
]

# Cues for 5 Root Cause categories
CAUSE_CUES = {
    "HUMAN": [
        "operator", "checklist", "handover", "fatigue", "training", "permit",
        "procedure", "skipped", "error", "communication", "bypassed", "contractor",
        "sign off", "inadequate training", "shift",
    ],
    "EQUIPMENT": [
        "mechanical", "seal", "bearing", "corrosion", "transmitter", "valve",
        "pump", "wear", "leak", "instrument", "pinhole", "vibration", "fatigue",
        "cracked", "calibration", "interlock", "gasket", "maintenance overdue",
    ],
    "PROCESS": [
        "temperature", "pressure", "cooling", "control loop", "excursion", "upset",
        "envelope", "flow", "relief", "feed", "catalyst", "contamination",
        "management of change", "overpressure",
    ],
    "ENVIRONMENTAL": [
        "rain", "lightning", "storm", "wind", "flooding", "ambient", "freeze",
        "heat wave", "weather", "external", "corrosion under insulation",
    ],
    "ACCIDENTAL": [
        "vehicle", "crane", "contractor", "dropped", "collision", "foreign object",
        "impact", "unplanned", "unforeseen",
    ],
}


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences cleanly."""
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def analyze_report(
    db: Session,
    incident: Incident,
    user: User | None = None,
    override_text: str | None = None,
) -> NLPAnalysis:
    """Run NLP analysis stub on an incident and persist results."""
    full_text = override_text if override_text else f"{incident.title}. {incident.description}"
    if incident.damage_details:
        full_text += f" Damage: {incident.damage_details}"
    if incident.immediate_actions:
        full_text += f" Immediate actions: {incident.immediate_actions}"

    lower_text = full_text.lower()
    sentences = _split_sentences(full_text)

    # 1. Determine Risk Level & Confidence
    critical_matches = [w for w in CRITICAL_CUES if w in lower_text]
    high_matches = [w for w in HIGH_CUES if w in lower_text]
    medium_matches = [w for w in MEDIUM_CUES if w in lower_text]
    low_matches = [w for w in LOW_CUES if w in lower_text]

    cues_found = []
    if incident.injuries >= 2 or critical_matches:
        risk_level = RiskLevel.CRITICAL
        confidence = 0.93
        cues_found = (critical_matches + high_matches)[:3] or ["multiple injuries" if incident.injuries >= 2 else "critical conditions"]
    elif incident.injuries == 1 or high_matches or incident.severity.value == "High":
        risk_level = RiskLevel.HIGH
        confidence = 0.88
        cues_found = (high_matches + medium_matches)[:3] or ["injury recorded" if incident.injuries == 1 else "high severity"]
    elif medium_matches or incident.severity.value == "Medium":
        risk_level = RiskLevel.MEDIUM
        confidence = 0.82
        cues_found = (medium_matches + low_matches)[:3] or ["operational excursion"]
    else:
        risk_level = RiskLevel.LOW
        confidence = 0.85
        cues_found = (low_matches or ["minor impact"])[:3]

    # 2. Extract Entities
    entities: list[dict[str, str]] = []
    if incident.incident_type:
        entities.append({"text": incident.incident_type, "label": "INCIDENT_TYPE"})
    for link in incident.equipment_links:
        if link.equipment:
            entities.append({"text": link.equipment.tag, "label": "EQUIPMENT"})

    # 3. Match Root Cause Categories
    all_causes = db.scalars(select(RootCause).where(RootCause.is_active == True)).all()  # noqa: E712
    cause_map = {c.code: c for c in all_causes}

    category_scores: list[tuple[str, int, str]] = []
    for code, keywords in CAUSE_CUES.items():
        matched_kws = [k for k in keywords if k in lower_text]
        score = len(matched_kws)
        # Find best evidence sentence
        best_sentence = ""
        for s in sentences:
            if any(k in s.lower() for k in matched_kws):
                best_sentence = s
                break
        if not best_sentence and sentences:
            best_sentence = sentences[0]
        category_scores.append((code, score, best_sentence))

    # Sort descending by score
    category_scores.sort(key=lambda x: x[1], reverse=True)

    # Pick top causes (always at least the highest scored, and second if score > 0)
    suggested_causes: list[dict[str, Any]] = []
    top_code, top_score, top_evidence = category_scores[0]
    top_conf = 0.89 if top_score > 0 else 0.72

    if top_code in cause_map:
        suggested_causes.append({
            "code": top_code,
            "root_cause_id": cause_map[top_code].id,
            "category": cause_map[top_code].name,
            "confidence": top_conf,
            "evidence": top_evidence or "Mentioned in incident description.",
        })

    second_code, second_score, second_evidence = category_scores[1]
    if second_score > 0 and second_code in cause_map and second_code != top_code:
        suggested_causes.append({
            "code": second_code,
            "root_cause_id": cause_map[second_code].id,
            "category": cause_map[second_code].name,
            "confidence": 0.65,
            "evidence": second_evidence or "Identified as secondary factor.",
        })

    # Fallback if no cause map matched
    if not suggested_causes and all_causes:
        first = all_causes[0]
        suggested_causes.append({
            "code": first.code,
            "root_cause_id": first.id,
            "category": first.name,
            "confidence": 0.60,
            "evidence": sentences[0] if sentences else "Initial report analysis.",
        })

    # Assemble JSON payload
    result = {
        "entities": entities,
        "root_causes": suggested_causes,
        "risk": {
            "level": risk_level.value,
            "confidence": confidence,
            "cues": cues_found,
        },
        "keywords": list(set(critical_matches + high_matches + medium_matches + low_matches))[:10],
    }

    # 4. Save NLPAnalysis record
    analysis = NLPAnalysis(
        incident_id=incident.id,
        model_version="stub-0.1",
        result=result,
        risk_level=risk_level,
        risk_confidence=confidence,
        created_by_id=user.id if user else None,
    )
    db.add(analysis)
    db.flush()

    # Update Incident risk properties
    incident.risk_level = risk_level
    incident.risk_confidence = confidence

    # 5. Populate IncidentRootCause suggestions
    # We update or create IncidentRootCause rows for source=NLP
    for sc in suggested_causes:
        rc_id = sc["root_cause_id"]
        existing = db.scalar(
            select(IncidentRootCause).where(
                IncidentRootCause.incident_id == incident.id,
                IncidentRootCause.root_cause_id == rc_id,
                IncidentRootCause.source == CauseSource.NLP,
            )
        )
        if existing:
            existing.confidence = sc["confidence"]
            existing.evidence = sc["evidence"]
            existing.analysis_id = analysis.id
            existing.review_status = ReviewStatus.SUGGESTED
        else:
            db.add(IncidentRootCause(
                incident_id=incident.id,
                root_cause_id=rc_id,
                source=CauseSource.NLP,
                confidence=sc["confidence"],
                evidence=sc["evidence"],
                review_status=ReviewStatus.SUGGESTED,
                analysis_id=analysis.id,
            ))

    db.flush()
    return analysis


def analyze_raw_text(
    db: Session,
    text: str,
    title: str = "",
    incident_type: str | None = None,
    severity: Severity = Severity.MEDIUM,
    injuries: int = 0,
) -> dict:
    """Analyze arbitrary incident text without creating an incident record."""
    full_text = f"{title}. {text}" if title else text
    lower_text = full_text.lower()
    sentences = _split_sentences(full_text)

    critical_matches = [w for w in CRITICAL_CUES if w in lower_text]
    high_matches = [w for w in HIGH_CUES if w in lower_text]
    medium_matches = [w for w in MEDIUM_CUES if w in lower_text]
    low_matches = [w for w in LOW_CUES if w in lower_text]

    cues_found = []
    if injuries >= 2 or critical_matches:
        risk_level = RiskLevel.CRITICAL
        confidence = 0.93
        cues_found = (critical_matches + high_matches)[:3] or ["multiple injuries" if injuries >= 2 else "critical conditions"]
    elif injuries == 1 or high_matches or (severity and severity.value == "High"):
        risk_level = RiskLevel.HIGH
        confidence = 0.88
        cues_found = (high_matches + medium_matches)[:3] or ["injury recorded" if injuries == 1 else "high severity"]
    elif medium_matches or (severity and severity.value == "Medium"):
        risk_level = RiskLevel.MEDIUM
        confidence = 0.82
        cues_found = (medium_matches + low_matches)[:3] or ["operational excursion"]
    else:
        risk_level = RiskLevel.LOW
        confidence = 0.85
        cues_found = (low_matches or ["minor impact"])[:3]

    entities: list[dict[str, str]] = []
    if incident_type:
        entities.append({"text": incident_type, "label": "INCIDENT_TYPE"})

    all_causes = db.scalars(select(RootCause).where(RootCause.is_active == True)).all()  # noqa: E712
    cause_map = {c.code: c for c in all_causes}

    category_scores: list[tuple[str, int, str]] = []
    for code, keywords in CAUSE_CUES.items():
        matched_kws = [k for k in keywords if k in lower_text]
        score = len(matched_kws)
        best_sentence = ""
        for s in sentences:
            if any(k in s.lower() for k in matched_kws):
                best_sentence = s
                break
        if not best_sentence and sentences:
            best_sentence = sentences[0]
        category_scores.append((code, score, best_sentence))

    category_scores.sort(key=lambda x: x[1], reverse=True)

    suggested_causes: list[dict[str, Any]] = []
    top_code, top_score, top_evidence = category_scores[0]
    top_conf = 0.89 if top_score > 0 else 0.72

    if top_code in cause_map:
        suggested_causes.append({
            "code": top_code,
            "root_cause_id": cause_map[top_code].id,
            "category": cause_map[top_code].name,
            "confidence": top_conf,
            "evidence": top_evidence or "Mentioned in incident description.",
        })

    second_code, second_score, second_evidence = category_scores[1]
    if second_score > 0 and second_code in cause_map and second_code != top_code:
        suggested_causes.append({
            "code": second_code,
            "root_cause_id": cause_map[second_code].id,
            "category": cause_map[second_code].name,
            "confidence": 0.65,
            "evidence": second_evidence or "Identified as secondary factor.",
        })

    if not suggested_causes and all_causes:
        first = all_causes[0]
        suggested_causes.append({
            "code": first.code,
            "root_cause_id": first.id,
            "category": first.name,
            "confidence": 0.60,
            "evidence": sentences[0] if sentences else "Initial report analysis.",
        })

    result = {
        "entities": entities,
        "root_causes": suggested_causes,
        "risk": {
            "level": risk_level.value,
            "confidence": confidence,
            "cues": cues_found,
        },
        "keywords": list(set(critical_matches + high_matches + medium_matches + low_matches))[:10],
    }

    return {
        "risk_level": risk_level,
        "risk_confidence": confidence,
        "result": result,
    }

