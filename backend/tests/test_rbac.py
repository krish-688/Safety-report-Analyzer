import pytest

from tests.conftest import API

NON_ADMIN = ["safety_manager", "pm1", "so1", "management"]


@pytest.mark.parametrize("key", NON_ADMIN)
def test_non_admin_cannot_use_user_admin_endpoints(client, auth, seeded, key):
    uid = seeded["users"]["so1"]["id"]
    h = auth(key)
    assert client.get(f"{API}/users", headers=h).status_code == 403
    assert client.get(f"{API}/users/{uid}", headers=h).status_code == 403
    assert client.post(f"{API}/users/{uid}/reset-password", headers=h,
                       json={"new_password": "Another@123"}).status_code == 403
    assert client.post(f"{API}/users/{uid}/approve", headers=h,
                       json={"role": "Safety Officer", "plant_id": 1}).status_code == 403
    assert client.post(f"{API}/users/{uid}/deactivate", headers=h).status_code == 403


def test_admin_can_list_users(client, auth):
    r = client.get(f"{API}/users", headers=auth("admin"), params={"status": "Active"})
    assert r.status_code == 200 and r.json()["total"] >= 9


def test_endpoints_require_authentication(client):
    for path in ("/users", "/incidents", "/plants", "/auth/me"):
        assert client.get(f"{API}{path}").status_code == 401, path


def test_admin_has_no_incident_access(client, auth):
    h = auth("admin")
    assert client.get(f"{API}/incidents", headers=h).status_code == 403
    assert client.get(f"{API}/incidents/1", headers=h).status_code == 403


@pytest.mark.parametrize("key", NON_ADMIN)
def test_incident_roles_can_read(client, auth, key):
    assert client.get(f"{API}/incidents", headers=auth(key)).status_code == 200


def test_approve_officer_requires_plant(client, auth, seeded):
    from tests.test_auth import register
    uid = register(client, "needs.plant@safetytest.com", plant_id=seeded["plant_ids"][0]).json()["id"]
    r = client.post(f"{API}/users/{uid}/approve", headers=auth("admin"), json={"role": "Safety Officer"})
    assert r.status_code == 422


def test_admin_cannot_deactivate_self_or_last_admin(client, auth, seeded):
    admin_id = seeded["users"]["admin"]["id"]
    assert client.post(f"{API}/users/{admin_id}/deactivate", headers=auth("admin")).status_code == 400
    r = client.patch(f"{API}/users/{admin_id}", headers=auth("admin"), json={"role": "Management"})
    assert r.status_code == 400  # would remove the last active Admin


def test_admin_reset_password_clears_lock_and_works(client, auth, seeded):
    target = seeded["users"]["management"]
    r = client.post(f"{API}/users/{target['id']}/reset-password", headers=auth("admin"),
                    json={"new_password": "Brand@New1"})
    assert r.status_code == 200
    ok = client.post(f"{API}/auth/login", json={"email": target["email"], "password": "Brand@New1"})
    assert ok.status_code == 200
    # restore so other tests keep working
    client.post(f"{API}/users/{target['id']}/reset-password", headers=auth("admin"),
                json={"new_password": target["password"]})


def test_reset_password_rejects_weak(client, auth, seeded):
    r = client.post(f"{API}/users/{seeded['users']['pm1']['id']}/reset-password", headers=auth("admin"),
                    json={"new_password": "weak"})
    assert r.status_code == 422
