import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite://"  # tests never touch the real database file

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import settings
from app.db import seed
from app.db.base import Base
from app.db.session import get_db
from app.main import app

API = settings.API_PREFIX
DEMO_PW = settings.SEED_DEMO_PASSWORD
ADMIN_PW = settings.SEED_ADMIN_PASSWORD


@pytest.fixture(scope="session")
def SessionTest():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session")
def seeded(SessionTest):
    """Seed once. Returns plain data (no ORM objects) about demo users and plants."""
    with SessionTest() as s:
        plants, causes, equipment = seed.seed_reference_data(s)
        users = seed.seed_users(s, plants)
        seed.seed_incidents(s, plants, causes, equipment, users)
        s.commit()
        return {
            "plant_ids": [p.id for p in plants],
            "users": {k: {"id": u.id, "email": u.email, "role": u.role, "plant_id": u.plant_id,
                          "password": ADMIN_PW if k == "admin" else DEMO_PW} for k, u in users.items()},
        }


@pytest.fixture(scope="session")
def client(SessionTest, seeded):
    def override():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def db(SessionTest):
    with SessionTest() as s:
        yield s


@pytest.fixture(scope="session")
def auth(client, seeded):
    """auth('so1') -> {'Authorization': 'Bearer ...'} (login once per demo user)."""
    cache: dict[str, dict] = {}

    def _auth(key: str) -> dict:
        if key not in cache:
            u = seeded["users"][key]
            r = client.post(f"{API}/auth/login", json={"email": u["email"], "password": u["password"]})
            assert r.status_code == 200, r.text
            cache[key] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[key]

    return _auth
