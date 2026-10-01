"""Stage 1 checks: schema creates and the seed produces a populated, consistent DB."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import seed
from app.db.base import Base
from app import models  # noqa: F401
from app.models import (
    Equipment, Incident, IncidentEquipment, IncidentRootCause, PlantUnit, RootCause, User,
)
from app.models.enums import UserRole


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        plants, causes, equipment = seed.seed_reference_data(s)
        users = seed.seed_users(s, plants)
        seed.seed_incidents(s, plants, causes, equipment, users)
        s.commit()
        yield s


def test_counts(db):
    assert db.scalar(select(func.count(PlantUnit.id))) == 3
    assert db.scalar(select(func.count(Equipment.id))) == 40
    assert db.scalar(select(func.count(RootCause.id))) == 5
    assert db.scalar(select(func.count(Incident.id))) == seed.N_INCIDENTS


def test_one_user_per_role(db):
    roles = {r for (r,) in db.execute(select(User.role))}
    assert roles == set(UserRole)


def test_all_five_cause_categories_used(db):
    used = db.scalar(select(func.count(func.distinct(IncidentRootCause.root_cause_id))))
    assert used == 5


def test_every_incident_has_equipment_in_same_plant(db):
    rows = db.execute(
        select(Incident.plant_id, Equipment.plant_id)
        .join(IncidentEquipment, IncidentEquipment.incident_id == Incident.id)
        .join(Equipment, Equipment.id == IncidentEquipment.equipment_id)
    ).all()
    assert rows and all(a == b for a, b in rows)


def test_incidents_spread_over_all_plants(db):
    plants = {p for (p,) in db.execute(select(Incident.plant_id))}
    assert len(plants) == 3
