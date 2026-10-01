from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models import User
from app.models.base import utcnow
from app.models.enums import UserRole, UserStatus
from tests.conftest import API


def register(client, email, role="Safety Officer", plant_id=None, password="Valid@1234"):
    return client.post(f"{API}/auth/register", json={
        "name": "Test User", "email": email, "password": password,
        "requested_role": role, "preferred_plant_id": plant_id})


def login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


@pytest.mark.parametrize("pw", ["Short1A", "alllowercase1", "ALLUPPERCASE1", "NoNumbersHere"])
def test_register_rejects_weak_password(client, seeded, pw):
    r = register(client, "weak@safetytest.com", plant_id=seeded["plant_ids"][0], password=pw)
    assert r.status_code == 422


def test_register_cannot_request_admin(client, seeded):
    r = register(client, "wannabe@safetytest.com", role="Admin", plant_id=seeded["plant_ids"][0])
    assert r.status_code == 422


def test_register_officer_requires_plant(client):
    assert register(client, "noplant@safetytest.com").status_code == 422


def test_register_pending_login_blocked_then_approved(client, seeded, auth):
    plant = seeded["plant_ids"][1]
    r = register(client, "new.officer@safetytest.com", plant_id=plant)
    assert r.status_code == 201 and r.json()["status"] == "Pending"

    assert register(client, "new.officer@safetytest.com", plant_id=plant).status_code == 409  # duplicate

    blocked = login(client, "new.officer@safetytest.com", "Valid@1234")
    assert blocked.status_code == 403 and "pending" in blocked.json()["detail"].lower()

    uid = r.json()["id"]
    ok = client.post(f"{API}/users/{uid}/approve", headers=auth("admin"),
                     json={"role": "Safety Officer", "plant_id": plant})
    assert ok.status_code == 200 and ok.json()["status"] == "Active"

    good = login(client, "new.officer@safetytest.com", "Valid@1234")
    assert good.status_code == 200
    body = good.json()
    assert body["user"]["role"] == "Safety Officer" and body["user"]["plant_id"] == plant


def test_rejected_and_inactive_blocked(client, seeded, auth):
    plant = seeded["plant_ids"][0]
    uid = register(client, "to.reject@safetytest.com", plant_id=plant).json()["id"]
    assert client.post(f"{API}/users/{uid}/reject", headers=auth("admin")).status_code == 200
    r = login(client, "to.reject@safetytest.com", "Valid@1234")
    assert r.status_code == 403 and "rejected" in r.json()["detail"].lower()

    uid2 = register(client, "to.deactivate@safetytest.com", plant_id=plant).json()["id"]
    client.post(f"{API}/users/{uid2}/approve", headers=auth("admin"),
                json={"role": "Safety Officer", "plant_id": plant})
    assert client.post(f"{API}/users/{uid2}/deactivate", headers=auth("admin")).status_code == 200
    r = login(client, "to.deactivate@safetytest.com", "Valid@1234")
    assert r.status_code == 403 and "deactivated" in r.json()["detail"].lower()


def test_wrong_password_and_unknown_email(client):
    assert login(client, "nobody@safetytest.com", "Whatever1").status_code == 401
    assert login(client, "admin@safety.local", "Wrong1234x").status_code == 401


def test_lockout_after_five_failures_and_unlock(client, db):
    db.add(User(name="Lock Me", email="lock@safetytest.com", password_hash=hash_password("Right@1234"),
                role=UserRole.SAFETY_MANAGER, status=UserStatus.ACTIVE))
    db.commit()

    codes = [login(client, "lock@safetytest.com", "Bad@12345").status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 423]

    # Even the right password is refused while locked.
    assert login(client, "lock@safetytest.com", "Right@1234").status_code == 423

    user = db.query(User).filter_by(email="lock@safetytest.com").one()
    db.refresh(user)  # pick up the lock written by the API's own session
    assert user.locked_until is not None
    user.locked_until = utcnow() - timedelta(minutes=1)  # lock expired
    db.commit()
    assert login(client, "lock@safetytest.com", "Right@1234").status_code == 200


def test_token_lifetime_is_30_minutes():
    token, expires_in = create_access_token(1, "Admin")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["exp"] - payload["iat"] == 30 * 60 and expires_in == 1800


def test_me_requires_valid_token(client, auth, seeded):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401

    expired, _ = create_access_token(seeded["users"]["so1"]["id"], "Safety Officer", timedelta(seconds=-5))
    r = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()

    me = client.get(f"{API}/auth/me", headers=auth("so1"))
    assert me.status_code == 200 and me.json()["email"] == seeded["users"]["so1"]["email"]


def test_logout(client, auth):
    assert client.post(f"{API}/auth/logout", headers=auth("so1")).status_code == 200
    assert client.post(f"{API}/auth/logout").status_code == 401


def test_register_options_public_and_never_offers_admin(client):
    r = client.get(f"{API}/auth/register-options")
    assert r.status_code == 200
    assert "Admin" not in r.json()["roles"] and len(r.json()["plants"]) == 3
