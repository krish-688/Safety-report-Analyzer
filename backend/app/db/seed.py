"""Seed script: python -m app.db.seed [--reset]

Creates: 3 plants, 40 equipment, 5 root-cause categories, thresholds, demo users,
~300 realistic fake incidents (with NLP-style analyses, investigations, actions, alerts).
"""
import argparse
import random
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine, init_db
from app.models import (
    Alert, AlertThreshold, AuditLog, CorrectiveAction, Equipment, Incident,
    IncidentEquipment, IncidentRootCause, Investigation, NLPAnalysis, PlantUnit,
    RootCause, User,
)
from app.models.base import utcnow
from app.models.enums import (
    ActionStatus, ActionType, AlertType, CauseSource, ReviewStatus, RiskLevel,
    Severity, UserRole, UserStatus, WorkflowStatus,
)

rng = random.Random(42)
N_INCIDENTS = 300

PLANTS = [
    ("Ethylene Cracker Plant", "ECP", "Jamnagar Complex, Gujarat"),
    ("Polymer Unit", "PLU", "Dahej Complex, Gujarat"),
    ("Aromatics & Refinery Unit", "ARU", "Panipat Complex, Haryana"),
]

CAUSES = [
    ("HUMAN", "Human Factors", "Operator error, inadequate training, fatigue, procedure not followed."),
    ("EQUIPMENT", "Equipment", "Mechanical failure, corrosion, instrument or seal failure, poor maintenance."),
    ("PROCESS", "Process", "Process upset, design or control deficiency, management of change gaps."),
    ("ENVIRONMENTAL", "Environmental", "Weather, lightning, flooding, extreme heat, external conditions."),
    ("ACCIDENTAL", "Accidental/Unplanned", "Unplanned release, third-party damage, unexpected ignition source."),
]

EQUIPMENT_TYPES = [
    ("P", "Centrifugal Pump"), ("E", "Heat Exchanger"), ("R", "Reactor"),
    ("C", "Distillation Column"), ("K", "Compressor"), ("T", "Storage Tank"),
    ("PSV", "Pressure Relief Valve"), ("F", "Furnace"), ("L", "Pipeline"),
    ("FL", "Flare Stack"), ("B", "Boiler"), ("CT", "Cooling Tower"),
]

THRESHOLDS = [
    ("equipment_incident_count", 3, "Incidents on the same equipment within the window that trigger a maintenance review"),
    ("equipment_window_months", 12, "Look-back window in months for the equipment threshold"),
    ("recurring_cause_count", 3, "Same root cause within one plant in the window that triggers a recurrence alert"),
    ("recurring_cause_window_days", 90, "Look-back window in days for recurring root cause alerts"),
    ("investigation_overdue_days", 0, "Grace days after due date before an investigation is flagged overdue"),
    ("action_overdue_days", 0, "Grace days after due date before an action is flagged overdue"),
]

# code -> list of (incident_type, title, description, immediate_actions, damage, keywords)
TEMPLATES = {
    "HUMAN": [
        ("Procedure Deviation", "Valve lined up incorrectly during startup",
         "During startup of {eq}, the operator opened the wrong isolation valve because the startup checklist was not followed. "
         "The shift handover did not mention the pending line-up change. Pressure rose above normal before the error was noticed.",
         "Line-up corrected, startup paused, supervisor notified.", "Minor gasket damage",
         ["operator error", "checklist", "handover", "startup"]),
        ("Permit Violation", "Hot work started without gas test",
         "A contractor began welding near {eq} before the gas test was completed. The permit issuer signed off without verifying field conditions. "
         "Fatigue after a long shift and inadequate training were noted by the supervisor.",
         "Work stopped, area gas tested, permit revoked.", "No damage",
         ["hot work", "permit", "fatigue", "training"]),
        ("Near Miss", "Incorrect sampling procedure at {eq}",
         "An operator skipped the depressurisation step while sampling from {eq}. Procedure was not followed due to time pressure and unclear instructions.",
         "Sample point isolated, operator retrained.", "None",
         ["sampling", "procedure", "time pressure"]),
    ],
    "EQUIPMENT": [
        ("Equipment Failure", "Mechanical seal leak on {eq}",
         "The mechanical seal on {eq} failed and released hydrocarbon vapour. Inspection found worn bearings and overdue preventive maintenance. "
         "Vibration readings had been trending upward for two weeks.",
         "Pump tripped, isolated and depressurised, area barricaded.", "Seal and bearing replaced",
         ["seal leak", "bearing wear", "vibration", "maintenance overdue"]),
        ("Loss of Containment", "Corrosion-related leak on {eq}",
         "A pinhole leak was found on {eq} caused by under-insulation corrosion. Thickness readings from the last inspection were below the alert limit. "
         "Small flammable release occurred at a flange.",
         "Unit shutdown, leak clamped, fire watch posted.", "Section replaced, 18 hours downtime",
         ["corrosion", "pinhole leak", "flange", "inspection"]),
        ("Instrument Failure", "Level transmitter failure on {eq}",
         "The level transmitter on {eq} failed high-reading, hiding an actual low level. The high-level alarm did not activate and the interlock was bypassed for testing. "
         "Equipment reliability and calibration records were incomplete.",
         "Manual level check, transmitter replaced.", "Instrument replaced",
         ["transmitter", "interlock bypass", "calibration", "alarm"]),
    ],
    "PROCESS": [
        ("Process Upset", "Runaway temperature excursion in {eq}",
         "Temperature in {eq} exceeded the design limit after a cooling water flow reduction. The control loop was poorly tuned and the operating envelope had changed "
         "without a management of change review. Emergency relief opened.",
         "Feed cut, emergency cooling applied, relief system monitored.", "Catalyst degradation",
         ["temperature excursion", "cooling water", "management of change", "relief"]),
        ("Overpressure", "Overpressure event on {eq}",
         "Pressure in {eq} rose rapidly when a downstream block valve closed. The design did not consider this blocked-outlet scenario and the hazard study was outdated. "
         "The relief valve lifted and the flare load was high.",
         "Feed reduced, valve reopened, flare monitored.", "Relief valve to be recalibrated",
         ["overpressure", "blocked outlet", "hazard study", "flare"]),
        ("Off-Spec Release", "Off-spec product routed to {eq}",
         "An off-spec stream was routed to {eq} due to a control system logic error after a software change. The process deviated from the approved design basis.",
         "Stream diverted, tank isolated, sampling done.", "Product downgrade",
         ["logic error", "software change", "off-spec", "design basis"]),
    ],
    "ENVIRONMENTAL": [
        ("Weather Event", "Lightning strike affecting {eq}",
         "A lightning strike during a thunderstorm caused a power dip and tripped {eq}. Surge protection was partially effective. "
         "Heavy rain also flooded a nearby drain trench.",
         "Unit brought to safe state, drains cleared.", "Damaged control card",
         ["lightning", "thunderstorm", "power dip", "flooding"]),
        ("Heat Stress", "Extreme heat impacts operation of {eq}",
         "During a heatwave, ambient temperature exceeded design conditions and {eq} ran at reduced efficiency. Two workers reported heat exhaustion during outdoor rounds.",
         "Workers rested and hydrated, rounds rescheduled.", "None",
         ["heatwave", "ambient temperature", "heat exhaustion"]),
        ("Flood", "Heavy rain flooding near {eq}",
         "Monsoon rain overwhelmed the stormwater drain near {eq}, submerging a motor control cabinet. Electrical supply was isolated and the area evacuated.",
         "Power isolated, water pumped out.", "Motor control cabinet replaced",
         ["monsoon", "flood", "drain", "electrical isolation"]),
    ],
    "ACCIDENTAL": [
        ("Unplanned Release", "Unexpected vapour release near {eq}",
         "An unexpected release of vapour occurred near {eq} with no clear initiating cause at the time. A portable gas detector alarmed and the area was cleared. "
         "Investigation found an unplanned venting from a drain valve left cracked open.",
         "Area evacuated, drain closed, gas monitoring.", "None",
         ["unplanned release", "vapour", "drain valve", "gas detector"]),
        ("Third-Party Damage", "Forklift struck pipe support near {eq}",
         "A contractor forklift accidentally struck a pipe support near {eq}, displacing a small-bore line. No leak occurred but the line was stressed.",
         "Line inspected, support repaired.", "Bent pipe support",
         ["forklift", "pipe support", "contractor", "collision"]),
        ("Fire", "Small fire from unexpected ignition at {eq}",
         "A small fire started on insulation soaked with oil near {eq}, ignited by an unexpected hot surface. The fire was extinguished by the plant fire team in minutes.",
         "Fire extinguished, insulation removed, area cooled.", "Insulation damaged",
         ["fire", "ignition", "oil-soaked insulation", "hot surface"]),
    ],
}

CAUSE_WEIGHTS = {"HUMAN": 0.26, "EQUIPMENT": 0.30, "PROCESS": 0.22, "ENVIRONMENTAL": 0.10, "ACCIDENTAL": 0.12}
NAMES = ["Aarav Sharma", "Priya Nair", "Rohan Mehta", "Sneha Iyer", "Vikram Rao", "Anita Desai", "Karan Malhotra"]


def reset_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def split_sentences(text: str) -> list[str]:
    return [s.strip() + "." for s in text.split(".") if s.strip()]


def seed_reference_data(db: Session):
    plants = [PlantUnit(name=n, code=c, location=l) for n, c, l in PLANTS]
    db.add_all(plants)
    causes = [RootCause(code=c, name=n, description=d) for c, n, d in CAUSES]
    db.add_all(causes)
    db.add_all(AlertThreshold(key=k, value=v, description=d) for k, v, d in THRESHOLDS)
    db.flush()

    equipment: list[Equipment] = []
    for i in range(40):
        prefix, etype = EQUIPMENT_TYPES[i % len(EQUIPMENT_TYPES)]
        plant = plants[i % 3]
        equipment.append(Equipment(
            tag=f"{prefix}-{100 + i}", name=f"{etype} {prefix}-{100 + i}", equipment_type=etype,
            plant_id=plant.id, installed_on=date(2005 + rng.randint(0, 17), rng.randint(1, 12), 1),
        ))
    db.add_all(equipment)
    db.flush()
    return plants, causes, equipment


def seed_users(db: Session, plants: list[PlantUnit]) -> dict[str, User]:
    def mk(key, name, email, role, plant, pw):
        return key, User(name=name, email=email, password_hash=hash_password(pw), role=role,
                         requested_role=role, status=UserStatus.ACTIVE,
                         plant_id=plant.id if plant else None,
                         preferred_plant_id=plant.id if plant else None)

    d, a = settings.SEED_DEMO_PASSWORD, settings.SEED_ADMIN_PASSWORD
    rows = [
        mk("admin", "System Admin", settings.SEED_ADMIN_EMAIL, UserRole.ADMIN, None, a),
        mk("safety_manager", "Suresh Kulkarni", "safety.manager@safety.local", UserRole.SAFETY_MANAGER, None, d),
        mk("management", "Meera Kapoor", "management@safety.local", UserRole.MANAGEMENT, None, d),
        mk("pm1", "Arjun Patel", "plant.manager@safety.local", UserRole.PLANT_MANAGER, plants[0], d),
        mk("so1", "Neha Verma", "officer@safety.local", UserRole.SAFETY_OFFICER, plants[0], d),
        mk("pm2", "Ravi Singh", "plant.manager2@safety.local", UserRole.PLANT_MANAGER, plants[1], d),
        mk("so2", "Kiran Joshi", "officer2@safety.local", UserRole.SAFETY_OFFICER, plants[1], d),
        mk("pm3", "Deepa Menon", "plant.manager3@safety.local", UserRole.PLANT_MANAGER, plants[2], d),
        mk("so3", "Imran Khan", "officer3@safety.local", UserRole.SAFETY_OFFICER, plants[2], d),
    ]
    users = dict(rows)
    db.add_all(users.values())
    db.flush()
    return users


def risk_from(severity: Severity, injuries: int, code: str) -> RiskLevel:
    score = {"Low": 1, "Medium": 2, "High": 3}[severity.value]
    score += 2 if injuries >= 2 else (1 if injuries else 0)
    score += 1 if code in ("PROCESS", "ACCIDENTAL") and rng.random() < 0.3 else 0
    if score <= 1:
        return RiskLevel.LOW
    if score == 2:
        return RiskLevel.MEDIUM
    if score == 3:
        return RiskLevel.HIGH if rng.random() < 0.5 else RiskLevel.MEDIUM
    return RiskLevel.HIGH if score == 4 else RiskLevel.CRITICAL


def status_for(age_days: int) -> WorkflowStatus:
    if age_days > 120:
        return rng.choices(list(WorkflowStatus), weights=[1, 1, 1, 2, 2, 93])[0]
    if age_days > 45:
        return rng.choices(list(WorkflowStatus), weights=[3, 12, 15, 20, 15, 35])[0]
    return rng.choices(list(WorkflowStatus), weights=[35, 30, 12, 10, 6, 7])[0]


def seed_incidents(db: Session, plants, causes, equipment, users) -> None:
    today = date.today()
    now = utcnow()
    cause_by_code = {c.code: c for c in causes}
    plant_users = {
        plants[0].id: ("so1", "pm1"), plants[1].id: ("so2", "pm2"), plants[2].id: ("so3", "pm3"),
    }
    # "Hot" equipment get more incidents so maintenance recommendations (3+ in 12 months) appear.
    weights = [5 if i in (0, 4, 7, 12, 19, 25, 31, 38) else 1 for i in range(len(equipment))]
    counter: dict[int, int] = {}
    plant_names = {p.id: p.name for p in plants}

    for n in range(N_INCIDENTS):
        code = rng.choices(list(CAUSE_WEIGHTS), weights=list(CAUSE_WEIGHTS.values()))[0]
        itype, title_t, desc_t, actions, damage, kws = rng.choice(TEMPLATES[code])
        primary_eq = rng.choices(equipment, weights=weights)[0]
        eqs = [primary_eq]
        if rng.random() < 0.25:
            same_plant = [e for e in equipment if e.plant_id == primary_eq.plant_id and e is not primary_eq]
            eqs.append(rng.choice(same_plant))
        plant_id = primary_eq.plant_id
        age_days = int(min(540, rng.triangular(0, 540, 120)))
        occurred = now - timedelta(days=age_days, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        severity = rng.choices(list(Severity), weights=[45, 38, 17])[0]
        injuries = 0 if severity == Severity.LOW else rng.choices([0, 1, 2, 3], weights=[70, 20, 7, 3])[0]
        risk = risk_from(severity, injuries, code)
        status = status_for(age_days)
        so_key, pm_key = plant_users[plant_id]
        year = occurred.year
        counter[year] = counter.get(year, 0) + 1

        inc = Incident(
            reference=f"INC-{year}-{counter[year]:04d}",
            title=title_t.format(eq=primary_eq.tag), occurred_at=occurred, plant_id=plant_id,
            incident_type=itype, description=desc_t.format(eq=primary_eq.tag), severity=severity,
            injuries=injuries, damage_details=damage, immediate_actions=actions,
            risk_level=risk, risk_confidence=round(rng.uniform(0.62, 0.96), 2), status=status,
            created_by_id=users[so_key].id, created_at=occurred + timedelta(hours=rng.randint(1, 8)),
        )
        db.add(inc)
        db.flush()
        for e in eqs:
            db.add(IncidentEquipment(incident_id=inc.id, equipment_id=e.id))
        db.add(AuditLog(user_id=users[so_key].id, action="incident.created", entity_type="incident",
                        entity_id=inc.id, details={"reference": inc.reference}, created_at=inc.created_at))

        # --- NLP-style analysis + root causes -------------------------------------------------
        sentences = split_sentences(inc.description)
        detected = [(code, round(rng.uniform(0.70, 0.95), 2))]
        if rng.random() < 0.3:
            other = rng.choice([c for c in CAUSE_WEIGHTS if c != code])
            detected.append((other, round(rng.uniform(0.40, 0.65), 2)))
        result = {
            "entities": [
                {"text": primary_eq.tag, "label": "EQUIPMENT"},
                {"text": itype, "label": "INCIDENT_TYPE"},
            ],
            "root_causes": [
                {"category": cause_by_code[c].name, "confidence": conf,
                 "evidence": sentences[min(i + 1, len(sentences) - 1)]}
                for i, (c, conf) in enumerate(detected)
            ],
            "risk": {"level": risk.value, "confidence": inc.risk_confidence, "cues": kws[:3]},
            "keywords": kws,
        }
        analysis = NLPAnalysis(incident_id=inc.id, model_version="seed", result=result,
                               risk_level=risk, risk_confidence=inc.risk_confidence,
                               created_by_id=users[so_key].id, created_at=inc.created_at + timedelta(hours=1))
        db.add(analysis)
        db.flush()
        confirmed = status not in (WorkflowStatus.REPORTED, WorkflowStatus.UNDER_INVESTIGATION)
        for i, (c, conf) in enumerate(detected):
            db.add(IncidentRootCause(
                incident_id=inc.id, root_cause_id=cause_by_code[c].id, source=CauseSource.NLP,
                confidence=conf, evidence=result["root_causes"][i]["evidence"],
                review_status=ReviewStatus.ACCEPTED if confirmed and i == 0 else ReviewStatus.SUGGESTED,
                reviewed_by_id=users[so_key].id if confirmed and i == 0 else None, analysis_id=analysis.id))
        if confirmed and rng.random() < 0.2:  # officer added a manual cause
            extra = rng.choice([c for c in CAUSE_WEIGHTS if c not in dict(detected)])
            db.add(IncidentRootCause(incident_id=inc.id, root_cause_id=cause_by_code[extra].id,
                                     source=CauseSource.MANUAL, review_status=ReviewStatus.ACCEPTED,
                                     reviewed_by_id=users[so_key].id))

        # --- Investigation + actions ----------------------------------------------------------
        if status != WorkflowStatus.REPORTED:
            due = (occurred + timedelta(days=rng.randint(14, 30))).date()
            inv = Investigation(
                incident_id=inc.id, investigator_id=users[so_key].id,
                assigned_by_id=users["safety_manager"].id, due_date=due,
                evidence="Photos, operator statements and DCS trend data collected." if confirmed else None,
                findings=f"Primary cause: {cause_by_code[code].name}." if confirmed else None,
                closed_at=(occurred + timedelta(days=rng.randint(10, 40))) if status == WorkflowStatus.CLOSED else None,
                verified_by_id=users["safety_manager"].id if status == WorkflowStatus.CLOSED else None,
                created_at=occurred + timedelta(days=1))
            db.add(inv)
            db.flush()
            if status in (WorkflowStatus.ACTION_PENDING, WorkflowStatus.VERIFICATION, WorkflowStatus.CLOSED):
                for _ in range(rng.randint(1, 3)):
                    atype = rng.choice(list(ActionType))
                    adue = (occurred + timedelta(days=rng.randint(20, 75))).date()
                    if status == WorkflowStatus.CLOSED:
                        ast, done = ActionStatus.COMPLETED, adue - timedelta(days=rng.randint(0, 10))
                    elif status == WorkflowStatus.VERIFICATION:
                        ast, done = ActionStatus.COMPLETED, adue - timedelta(days=rng.randint(0, 5))
                    else:
                        ast = rng.choice([ActionStatus.PROPOSED, ActionStatus.APPROVED, ActionStatus.IN_PROGRESS, ActionStatus.COMPLETED])
                        done = adue if ast == ActionStatus.COMPLETED else None
                    db.add(CorrectiveAction(
                        incident_id=inc.id, investigation_id=inv.id, action_type=atype,
                        description=rng.choice([
                            f"Revise SOP for {primary_eq.tag} and retrain operators.",
                            f"Inspect and replace worn components on {primary_eq.tag}.",
                            f"Add interlock and alarm review for {primary_eq.tag}.",
                            "Update hazard study and management of change records.",
                            "Install additional gas detectors and review drain practices.",
                        ]),
                        owner_id=users[so_key].id, equipment_id=primary_eq.id, due_date=adue, status=ast,
                        approved_by_id=users[pm_key].id if ast != ActionStatus.PROPOSED else None,
                        completed_at=datetime.combine(done, datetime.min.time()) if done else None))

        # --- Alerts for recent serious incidents ----------------------------------------------
        if age_days <= 30 and risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            critical = risk == RiskLevel.CRITICAL
            recipients = [users[pm_key], users["safety_manager"]] + ([users["management"]] if critical else [])
            for r in recipients:
                db.add(Alert(
                    user_id=r.id, alert_type=AlertType.CRITICAL_INCIDENT if critical else AlertType.HIGH_RISK_INCIDENT,
                    title=f"{risk.value.title()} incident {inc.reference}",
                    message=f"{inc.title} at {plant_names[plant_id]}.", incident_id=inc.id,
                    is_read=rng.random() < 0.4, created_at=inc.created_at))


def run(reset: bool = False) -> None:
    if reset:
        reset_db()
    else:
        init_db()
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            print("Database already has data. Use --reset to wipe and reseed.")
            return
        plants, causes, equipment = seed_reference_data(db)
        users = seed_users(db, plants)
        seed_incidents(db, plants, causes, equipment, users)
        db.add(AuditLog(user_id=users["admin"].id, action="seed.run", entity_type="system",
                        details={"incidents": N_INCIDENTS}))
        db.commit()
        print(f"Seeded {len(plants)} plants, {len(equipment)} equipment, {len(causes)} root causes, "
              f"{len(users)} users, {N_INCIDENTS} incidents.")
        print(f"\nAdmin : {settings.SEED_ADMIN_EMAIL} / {settings.SEED_ADMIN_PASSWORD}")
        print(f"Others: password '{settings.SEED_DEMO_PASSWORD}' for:")
        for u in users.values():
            if u.role != UserRole.ADMIN:
                print(f"  {u.role.value:15} {u.email}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop all tables and reseed")
    run(ap.parse_args().reset)
