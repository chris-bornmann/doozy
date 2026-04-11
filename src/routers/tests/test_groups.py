
import pytest
from sqlmodel import Session

from constants import FriendshipStatus
from db.models import Friendship, Group, GroupMember
from db.users import create_user
from util.security import encode_token
from app.main import app
from db.main import get_session
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session: Session, username: str):
    """Create an authenticated (TestClient, user) pair."""
    user = create_user(session, username=username, password="password1234")
    token = encode_token({"sub": user.username})
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(
        app,
        raise_server_exceptions=True,
        headers={"Authorization": f"Bearer {token}"},
    )
    return client, user


def _make_friends(session: Session, user_a_id: int, user_b_id: int):
    """Seed an accepted friendship between two users."""
    f = Friendship(
        requester_id=user_a_id,
        addressee_id=user_b_id,
        status=FriendshipStatus.ACCEPTED,
    )
    session.add(f)
    session.commit()


def _seed_group(session: Session, name: str, owner_id: int, member_ids: list[int] = []) -> Group:
    """Create a group with the owner and any extra members pre-added."""
    group = Group(name=name, owner_id=owner_id)
    session.add(group)
    session.flush()
    session.add(GroupMember(group_id=group.id, user_id=owner_id))
    for uid in member_ids:
        session.add(GroupMember(group_id=group.id, user_id=uid))
    session.commit()
    session.refresh(group)
    return group


# ---------------------------------------------------------------------------
# POST /groups/
# ---------------------------------------------------------------------------

def test_create_group(auth_headers):
    client, user = auth_headers
    resp = client.post("/groups/", json={"name": "My Test Group"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Test Group"
    assert data["owner"] == user.username
    assert user.username in data["members"]


def test_create_group_owner_auto_added_as_member(auth_headers):
    client, user = auth_headers
    resp = client.post("/groups/", json={"name": "Auto Member Group"})
    assert resp.status_code == 201
    assert user.username in resp.json()["members"]


def test_create_duplicate_name_returns_409(auth_headers):
    client, _ = auth_headers
    client.post("/groups/", json={"name": "Duplicate Group!"})
    resp = client.post("/groups/", json={"name": "Duplicate Group!"})
    assert resp.status_code == 409


def test_create_requires_auth(client):
    resp = client.post("/groups/", json={"name": "No Auth Group!"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /groups/
# ---------------------------------------------------------------------------

def test_list_groups_includes_owned(auth_headers, session):
    client, user = auth_headers
    _seed_group(session, "My Owned Group!", user.id)
    ids = [g["id"] for g in client.get("/groups/").json()["items"]]
    assert any(True for g in client.get("/groups/").json()["items"] if g["name"] == "My Owned Group!")


def test_list_groups_includes_joined(auth_headers, session):
    client, user = auth_headers
    _, owner = _make_user(session, "groupowner1234")
    group = _seed_group(session, "Joined Group Name!", owner.id, member_ids=[user.id])
    names = [g["name"] for g in client.get("/groups/").json()["items"]]
    assert "Joined Group Name!" in names


def test_list_groups_excludes_others(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "groupowner1235")
    _seed_group(session, "Not My Group Name!", other.id)
    names = [g["name"] for g in client.get("/groups/").json()["items"]]
    assert "Not My Group Name!" not in names


def test_list_groups_requires_auth(client):
    assert client.get("/groups/").status_code == 401


# ---------------------------------------------------------------------------
# GET /groups/{id}
# ---------------------------------------------------------------------------

def test_get_group_as_member(auth_headers, session):
    client, user = auth_headers
    group = _seed_group(session, "Get Group Test!!", user.id)
    resp = client.get(f"/groups/{group.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Get Group Test!!"
    assert user.username in data["members"]


def test_get_group_not_member_returns_403(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "groupowner1236")
    group = _seed_group(session, "Private Group Name!", other.id)
    assert client.get(f"/groups/{group.id}").status_code == 403


def test_get_group_not_found_returns_404(auth_headers):
    client, _ = auth_headers
    assert client.get("/groups/99999").status_code == 404


# ---------------------------------------------------------------------------
# DELETE /groups/{id}
# ---------------------------------------------------------------------------

def test_delete_group_as_owner(auth_headers, session):
    client, user = auth_headers
    group = _seed_group(session, "Delete Me Group!!", user.id)
    resp = client.delete(f"/groups/{group.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_delete_group_as_member_returns_403(auth_headers, session):
    client, user = auth_headers
    _, owner = _make_user(session, "groupowner1237")
    group = _seed_group(session, "Cannot Delete Me!", owner.id, member_ids=[user.id])
    assert client.delete(f"/groups/{group.id}").status_code == 403


def test_delete_group_requires_auth(client, session):
    _, owner = _make_user(session, "groupowner1238")
    group = _seed_group(session, "Auth Delete Test!!", owner.id)
    assert client.delete(f"/groups/{group.id}").status_code == 401


# ---------------------------------------------------------------------------
# POST /groups/{id}/members/{username}
# ---------------------------------------------------------------------------

def test_add_friend_to_group(auth_headers, session):
    client, user = auth_headers
    _, friend = _make_user(session, "groupfriend1234")
    _make_friends(session, user.id, friend.id)
    group = _seed_group(session, "Add Member Group!!", user.id)
    resp = client.post(f"/groups/{group.id}/members/{friend.username}")
    assert resp.status_code == 200
    assert friend.username in resp.json()["members"]


def test_add_non_friend_returns_403(auth_headers, session):
    client, user = auth_headers
    _, stranger = _make_user(session, "groupstranger123")
    group = _seed_group(session, "No Stranger Group!", user.id)
    assert client.post(f"/groups/{group.id}/members/{stranger.username}").status_code == 403


def test_add_already_member_returns_409(auth_headers, session):
    client, user = auth_headers
    _, friend = _make_user(session, "groupfriend1235")
    _make_friends(session, user.id, friend.id)
    group = _seed_group(session, "Already Member Grp!", user.id, member_ids=[friend.id])
    assert client.post(f"/groups/{group.id}/members/{friend.username}").status_code == 409


def test_add_member_as_non_owner_returns_403(auth_headers, session):
    client, user = auth_headers
    _, owner = _make_user(session, "groupowner1239")
    _, friend = _make_user(session, "groupfriend1236")
    group = _seed_group(session, "Non Owner Add Grp!", owner.id, member_ids=[user.id])
    assert client.post(f"/groups/{group.id}/members/{friend.username}").status_code == 403


def test_add_unknown_user_returns_404(auth_headers, session):
    client, user = auth_headers
    group = _seed_group(session, "Unknown User Group!", user.id)
    assert client.post(f"/groups/{group.id}/members/nosuchuser99").status_code == 404


# ---------------------------------------------------------------------------
# DELETE /groups/{id}/members/{username}
# ---------------------------------------------------------------------------

def test_remove_member_as_owner(auth_headers, session):
    client, user = auth_headers
    _, member = _make_user(session, "groupmember1234")
    group = _seed_group(session, "Remove Member Grp!", user.id, member_ids=[member.id])
    resp = client.delete(f"/groups/{group.id}/members/{member.username}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_remove_self_as_owner_returns_409(auth_headers, session):
    client, user = auth_headers
    group = _seed_group(session, "Cannot Remove Self!", user.id)
    assert client.delete(f"/groups/{group.id}/members/{user.username}").status_code == 409


def test_remove_member_as_non_owner_returns_403(auth_headers, session):
    client, user = auth_headers
    _, owner = _make_user(session, "groupowner1240")
    _, other = _make_user(session, "groupmember1235")
    group = _seed_group(session, "Non Owner Remove!!", owner.id, member_ids=[user.id, other.id])
    assert client.delete(f"/groups/{group.id}/members/{other.username}").status_code == 403


def test_remove_non_member_returns_404(auth_headers, session):
    client, user = auth_headers
    _, non_member = _make_user(session, "groupmember1236")
    group = _seed_group(session, "Non Member Remove!", user.id)
    assert client.delete(f"/groups/{group.id}/members/{non_member.username}").status_code == 404
