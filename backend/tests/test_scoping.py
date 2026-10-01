from sqlalchemy import func, select

from app.models import Incident, User
from app.models.enums import UserRole
from app.services.incident_service import get_incident_or_404, scope_incident_query
from tests.conftest import API


def _count(db, plant_id=None):
    stmt = select(func.count(Incident.id))
    if plant_id:
        stmt = stmt.where(Incident.plant_id == plant_id)
    return db.scalar(stmt)


def _all_ids(client, headers):
    ids, page = [], 1
    while True:
        r = client.get(f"{API}/incidents", headers=headers, params={"page": page, "size": 200})
        body = r.json()
        ids += [(i["id"], i["plant_id"]) for i in body["items"]]
        if len(ids) >= body["total"]:
            return ids, body["total"]
        page += 1


def test_officer_sees_only_own_plant(client, auth, seeded, db):
    plant = seeded["users"]["so1"]["plant_id"]
    ids, total = _all_ids(client, auth("so1"))
    assert total == _count(db, plant) > 0
    assert {p for _, p in ids} == {plant}


def test_plant_manager_scoped_to_their_plant(client, auth, seeded, db):
    plant = seeded["users"]["pm2"]["plant_id"]
    ids, total = _all_ids(client, auth("pm2"))
    assert total == _count(db, plant)
    assert {p for _, p in ids} == {plant}


def test_global_roles_see_all_plants(client, auth, db):
    for key in ("safety_manager", "management"):
        _, total = _all_ids(client, auth(key))
        assert total == _count(db)


def test_cross_plant_access_returns_404(client, auth, seeded, db):
    other_plant = seeded["users"]["so2"]["plant_id"]
    foreign_id = db.scalar(select(Incident.id).where(Incident.plant_id == other_plant))
    assert client.get(f"{API}/incidents/{foreign_id}", headers=auth("so1")).status_code == 404
    assert client.get(f"{API}/incidents/{foreign_id}", headers=auth("pm1")).status_code == 404
    assert client.get(f"{API}/incidents/{foreign_id}", headers=auth("so2")).status_code == 200
    assert client.get(f"{API}/incidents/{foreign_id}", headers=auth("safety_manager")).status_code == 200


def test_scope_function_directly(db, seeded):
    def user(role, plant_id):
        return User(id=-1, role=role, plant_id=plant_id)

    p1 = seeded["plant_ids"][0]
    own = db.scalars(scope_incident_query(user(UserRole.SAFETY_OFFICER, p1))).all()
    assert own and all(i.plant_id == p1 for i in own)
    assert db.scalars(scope_incident_query(user(UserRole.ADMIN, None))).all() == []
    assert db.scalars(scope_incident_query(user(UserRole.PLANT_MANAGER, None))).all() == []  # no plant -> nothing
    assert len(db.scalars(scope_incident_query(user(UserRole.MANAGEMENT, None))).all()) == _count(db)


def test_scope_function_composes_with_filters(db, seeded):
    p1 = seeded["plant_ids"][0]
    stmt = scope_incident_query(User(id=-1, role=UserRole.SAFETY_OFFICER, plant_id=p1),
                                select(Incident).where(Incident.plant_id == seeded["plant_ids"][1]))
    assert db.scalars(stmt).all() == []  # a filter can never widen the scope
