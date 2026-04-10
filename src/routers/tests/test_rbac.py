"""
Integration tests for Casbin RBAC enforcement.

Covers the two-gate model:
  Gate 1 (Casbin): does the user's role permit the action on this resource type?
  Gate 2 (ownership): does the user own this specific item instance?
"""

from db.models import Item
from db.users import create_user
from rbac.roles import assign_role
from util.security import encode_token
from app.main import app
from db.main import get_session
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Tag management: admin-only write/delete
# ---------------------------------------------------------------------------

def test_user_cannot_create_tag(auth_headers):
    client, _ = auth_headers
    assert client.post("/tags/", json={"name": "notallowed"}).status_code == 403


def test_user_cannot_delete_tag(admin_client, auth_headers):
    admin, _ = admin_client
    tag_id = admin.post("/tags/", json={"name": "todelete"}).json()["id"]
    user_client, _ = auth_headers
    assert user_client.delete(f"/tags/{tag_id}").status_code == 403


def test_admin_can_create_tag(admin_client):
    client, _ = admin_client
    assert client.post("/tags/", json={"name": "adminmade"}).status_code == 200


def test_admin_can_delete_tag(admin_client):
    client, _ = admin_client
    tag_id = client.post("/tags/", json={"name": "gone"}).json()["id"]
    assert client.delete(f"/tags/{tag_id}").status_code == 200


# ---------------------------------------------------------------------------
# Item ownership: Gate 2 still enforced after Gate 1 passes
# ---------------------------------------------------------------------------

def test_user_cannot_read_other_users_item(auth_headers, session):
    """Gate 1 passes (user role allows items:read), Gate 2 blocks (not owner)."""
    other = create_user(session, username="otheruser1", password="password1234")
    item = Item(name="Other persons item", creator_id=other.id)
    session.add(item)
    session.commit()
    session.refresh(item)

    client, _ = auth_headers
    assert client.get(f"/items/{item.id}").status_code == 403


def test_user_can_read_own_item(auth_headers, session):
    client, user = auth_headers
    item = Item(name="My own item abcde", creator_id=user.id)
    session.add(item)
    session.commit()
    session.refresh(item)

    assert client.get(f"/items/{item.id}").status_code == 200


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------

def test_unauthenticated_cannot_access_items(client):
    assert client.get("/items/").status_code == 401


def test_unauthenticated_cannot_create_item(client):
    assert client.post("/items/", data={"name": "test item abc", "state": "NEW"}).status_code == 401


# ---------------------------------------------------------------------------
# Multiple roles: a user with both "user" and "admin" can do everything
# ---------------------------------------------------------------------------

def test_user_with_admin_role_can_create_tag(session):
    """A user assigned the admin role (in addition to user) can write tags."""
    user = create_user(session, username="poweruser1", password="password1234")
    assign_role(session, user.id, "admin")
    token = encode_token({"sub": user.username})
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=True, headers={"Authorization": f"Bearer {token}"})
    try:
        assert client.post("/tags/", json={"name": "multirole"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
