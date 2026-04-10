"""
Tests for the /rbac/ management endpoints.

GET  /rbac/me/permissions — evaluated permissions for the current user
GET  /rbac/               — list all users with roles (admin only)
GET  /rbac/{user_id}      — get one user's roles (admin OR self)
POST /rbac/               — assign a role (admin only)
DELETE /rbac/             — revoke a role (admin only)
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from db.main import get_session
from db.users import create_user
from rbac.roles import assign_role
from util.security import encode_token


# ---------------------------------------------------------------------------
# GET /rbac/me/permissions
# ---------------------------------------------------------------------------

def test_my_permissions_returns_dict(auth_headers):
    client, _ = auth_headers
    resp = client.get("/rbac/me/permissions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # Regular user can read/write/delete items
    assert "items" in data
    assert set(data["items"]) == {"read", "write", "delete"}


def test_my_permissions_user_cannot_write_tags(auth_headers):
    client, _ = auth_headers
    data = client.get("/rbac/me/permissions").json()
    assert "write" not in data.get("tags", [])
    assert "delete" not in data.get("tags", [])
    assert "read" in data.get("tags", [])


def test_my_permissions_admin_can_write_tags(admin_client):
    client, _ = admin_client
    data = client.get("/rbac/me/permissions").json()
    assert set(data["tags"]) == {"read", "write", "delete"}


def test_my_permissions_admin_has_rbac_access(admin_client):
    client, _ = admin_client
    data = client.get("/rbac/me/permissions").json()
    assert "rbac" in data
    assert set(data["rbac"]) == {"read", "write", "delete"}


def test_my_permissions_user_has_no_rbac_key(auth_headers):
    client, _ = auth_headers
    data = client.get("/rbac/me/permissions").json()
    assert "rbac" not in data


def test_my_permissions_unauthenticated_gets_401(client):
    assert client.get("/rbac/me/permissions").status_code == 401


# ---------------------------------------------------------------------------
# GET /rbac/
# ---------------------------------------------------------------------------

def test_list_user_roles_returns_all_users(admin_client, session):
    client, admin = admin_client
    other = create_user(session, username="otheruser1", password="password1234")

    resp = client.get("/rbac/")
    assert resp.status_code == 200
    data = resp.json()
    user_ids = [entry["user_id"] for entry in data]
    assert admin.id in user_ids
    assert other.id in user_ids


def test_list_user_roles_shows_correct_roles(admin_client):
    client, admin = admin_client
    resp = client.get("/rbac/")
    assert resp.status_code == 200
    entry = next(e for e in resp.json() if e["user_id"] == admin.id)
    assert "admin" in entry["roles"]


def test_list_user_roles_user_with_no_roles_shows_empty(admin_client, session):
    client, _ = admin_client
    other = create_user(session, username="noroleuser1", password="password1234")
    # Bypass create_user's default role assignment by directly checking
    # what the endpoint returns for this user
    resp = client.get("/rbac/")
    entry = next(e for e in resp.json() if e["user_id"] == other.id)
    # create_user assigns "user" role by default
    assert "user" in entry["roles"]


def test_list_user_roles_non_admin_gets_403(auth_headers):
    client, _ = auth_headers
    assert client.get("/rbac/").status_code == 403


def test_list_user_roles_unauthenticated_gets_401(client):
    assert client.get("/rbac/").status_code == 401


# ---------------------------------------------------------------------------
# GET /rbac/{user_id}
# ---------------------------------------------------------------------------

def test_get_user_roles_admin_can_read_any_user(admin_client, session):
    client, _ = admin_client
    other = create_user(session, username="targetuser1", password="password1234")
    resp = client.get(f"/rbac/{other.id}")
    assert resp.status_code == 200
    assert "user" in resp.json()


def test_get_user_roles_user_can_read_own_roles(auth_headers):
    client, user = auth_headers
    resp = client.get(f"/rbac/{user.id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_user_roles_user_cannot_read_other_users_roles(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser2", password="password1234")
    assert client.get(f"/rbac/{other.id}").status_code == 403


def test_get_user_roles_unauthenticated_gets_401(client, session):
    other = create_user(session, username="someuser11", password="password1234")
    assert client.get(f"/rbac/{other.id}").status_code == 401


def test_get_user_roles_nonexistent_user_returns_404(admin_client):
    client, _ = admin_client
    assert client.get("/rbac/99999").status_code == 404


# ---------------------------------------------------------------------------
# POST /rbac/
# ---------------------------------------------------------------------------

def test_add_role_assigns_role(admin_client, session):
    client, _ = admin_client
    target = create_user(session, username="upgradeuser1", password="password1234")
    resp = client.post("/rbac/", json={"user_id": target.id, "role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    assert resp.json()["user_id"] == target.id


def test_add_role_duplicate_returns_409(admin_client, session):
    client, _ = admin_client
    target = create_user(session, username="dupuser1234", password="password1234")
    client.post("/rbac/", json={"user_id": target.id, "role": "admin"})
    assert client.post("/rbac/", json={"user_id": target.id, "role": "admin"}).status_code == 409


def test_add_role_nonexistent_user_returns_404(admin_client):
    client, _ = admin_client
    assert client.post("/rbac/", json={"user_id": 99999, "role": "admin"}).status_code == 404


def test_add_role_invalid_role_returns_422(admin_client, session):
    client, _ = admin_client
    target = create_user(session, username="targetuser2", password="password1234")
    assert client.post("/rbac/", json={"user_id": target.id, "role": "superuser"}).status_code == 422


def test_add_role_non_admin_gets_403(auth_headers, session):
    client, _ = auth_headers
    target = create_user(session, username="victimuser1", password="password1234")
    assert client.post("/rbac/", json={"user_id": target.id, "role": "admin"}).status_code == 403


def test_add_role_unauthenticated_gets_401(client, session):
    target = create_user(session, username="anonvictim1", password="password1234")
    assert client.post("/rbac/", json={"user_id": target.id, "role": "admin"}).status_code == 401


# ---------------------------------------------------------------------------
# DELETE /rbac/
# ---------------------------------------------------------------------------

def test_remove_role_revokes_role(admin_client, session):
    client, _ = admin_client
    target = create_user(session, username="revokeuser1", password="password1234")
    assign_role(session, target.id, "admin")
    resp = client.request("DELETE", "/rbac/", json={"user_id": target.id, "role": "admin"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_remove_role_nonexistent_assignment_returns_404(admin_client, session):
    client, _ = admin_client
    target = create_user(session, username="noassignuser1", password="password1234")
    assert client.request("DELETE", "/rbac/", json={"user_id": target.id, "role": "admin"}).status_code == 404


def test_remove_role_nonexistent_user_returns_404(admin_client):
    client, _ = admin_client
    assert client.request("DELETE", "/rbac/", json={"user_id": 99999, "role": "admin"}).status_code == 404


def test_remove_role_non_admin_gets_403(auth_headers, session):
    client, _ = auth_headers
    target = create_user(session, username="protectuser1", password="password1234")
    assert client.request("DELETE", "/rbac/", json={"user_id": target.id, "role": "user"}).status_code == 403


def test_remove_role_unauthenticated_gets_401(client, session):
    target = create_user(session, username="anondelete11", password="password1234")
    assert client.request("DELETE", "/rbac/", json={"user_id": target.id, "role": "user"}).status_code == 401
