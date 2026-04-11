
import pytest
from sqlmodel import Session

from constants import FriendshipStatus
from db.models import Friendship
from db.users import create_user
from util.security import encode_token
from app.main import app
from db.main import get_session
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session: Session, username: str):
    """Create a second user and return (TestClient, user) authenticated as them."""
    user = create_user(session, username=username, password="password1234")
    token = encode_token({"sub": user.username})
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(
        app,
        raise_server_exceptions=True,
        headers={"Authorization": f"Bearer {token}"},
    )
    return client, user


def _seed_friendship(session: Session, requester_id: int, addressee_id: int,
                     status: FriendshipStatus = FriendshipStatus.PENDING) -> Friendship:
    f = Friendship(requester_id=requester_id, addressee_id=addressee_id, status=status)
    session.add(f)
    session.commit()
    session.refresh(f)
    return f


# ---------------------------------------------------------------------------
# POST /friends/request/{username}
# ---------------------------------------------------------------------------

def test_request_friend(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1234")
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 201
    data = resp.json()
    assert data["requester"] == user.username
    assert data["addressee"] == other.username
    assert data["status"] == FriendshipStatus.PENDING


def test_request_self_returns_400(auth_headers):
    client, user = auth_headers
    resp = client.post(f"/friends/request/{user.username}")
    assert resp.status_code == 400


def test_request_nonexistent_user_returns_404(auth_headers):
    client, _ = auth_headers
    resp = client.post("/friends/request/nosuchuser9")
    assert resp.status_code == 404


def test_request_duplicate_pending_returns_409(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1235")
    _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 409


def test_request_already_friends_returns_409(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1236")
    _seed_friendship(session, user.id, other.id, FriendshipStatus.ACCEPTED)
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 409


def test_request_when_other_sent_pending_returns_409(auth_headers, session):
    """If the other user already sent me a request, I can't send one back."""
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1237")
    _seed_friendship(session, other.id, user.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 409


def test_request_after_decline_resends(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1238")
    _seed_friendship(session, user.id, other.id, FriendshipStatus.DECLINED)
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 201
    assert resp.json()["status"] == FriendshipStatus.PENDING


def test_request_requires_auth(client, session):
    _, other = _make_user(session, "otheruser1239")
    resp = client.post(f"/friends/request/{other.username}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /friends/{id}/accept
# ---------------------------------------------------------------------------

def test_accept_friendship(auth_headers, session):
    client, user = auth_headers
    other_client, other = _make_user(session, "otheruser1240")
    f = _seed_friendship(session, other.id, user.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/{f.id}/accept")
    assert resp.status_code == 200
    assert resp.json()["status"] == FriendshipStatus.ACCEPTED


def test_accept_as_requester_returns_403(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1241")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/{f.id}/accept")
    assert resp.status_code == 403


def test_accept_non_pending_returns_409(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1242")
    f = _seed_friendship(session, other.id, user.id, FriendshipStatus.DECLINED)
    resp = client.post(f"/friends/{f.id}/accept")
    assert resp.status_code == 409


def test_accept_not_found_returns_404(auth_headers):
    client, _ = auth_headers
    resp = client.post("/friends/99999/accept")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /friends/{id}/decline
# ---------------------------------------------------------------------------

def test_decline_friendship(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1243")
    f = _seed_friendship(session, other.id, user.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/{f.id}/decline")
    assert resp.status_code == 200
    assert resp.json()["status"] == FriendshipStatus.DECLINED


def test_decline_as_requester_returns_403(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1244")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    resp = client.post(f"/friends/{f.id}/decline")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /friends/
# ---------------------------------------------------------------------------

def test_list_friends_returns_accepted(auth_headers, session):
    client, user = auth_headers
    _, friend = _make_user(session, "otheruser1245")
    _, stranger = _make_user(session, "otheruser1246")
    _seed_friendship(session, user.id, friend.id, FriendshipStatus.ACCEPTED)
    _seed_friendship(session, user.id, stranger.id, FriendshipStatus.PENDING)
    resp = client.get("/friends/")
    assert resp.status_code == 200
    ids = [u["id"] for u in resp.json()["items"]]
    assert friend.id in ids
    assert stranger.id not in ids


def test_list_friends_includes_both_directions(auth_headers, session):
    """User appears in friends list whether they were the requester or addressee."""
    client, user = auth_headers
    _, friend = _make_user(session, "otheruser1247")
    _seed_friendship(session, friend.id, user.id, FriendshipStatus.ACCEPTED)
    ids = [u["id"] for u in client.get("/friends/").json()["items"]]
    assert friend.id in ids


def test_list_friends_requires_auth(client):
    assert client.get("/friends/").status_code == 401


# ---------------------------------------------------------------------------
# GET /friends/pending
# ---------------------------------------------------------------------------

def test_list_pending_returns_incoming(auth_headers, session):
    client, user = auth_headers
    _, sender = _make_user(session, "otheruser1248")
    f = _seed_friendship(session, sender.id, user.id, FriendshipStatus.PENDING)
    resp = client.get("/friends/pending")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["items"]]
    assert f.id in ids


def test_list_pending_excludes_sent(auth_headers, session):
    """Requests I sent do not appear in /pending."""
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1249")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    ids = [r["id"] for r in client.get("/friends/pending").json()["items"]]
    assert f.id not in ids


# ---------------------------------------------------------------------------
# GET /friends/sent
# ---------------------------------------------------------------------------

def test_list_sent_returns_outgoing(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1250")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    resp = client.get("/friends/sent")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["items"]]
    assert f.id in ids


def test_list_sent_includes_declined(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1251")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.DECLINED)
    ids = [r["id"] for r in client.get("/friends/sent").json()["items"]]
    assert f.id in ids


# ---------------------------------------------------------------------------
# DELETE /friends/{id}
# ---------------------------------------------------------------------------

def test_remove_friendship_by_requester(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1252")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.ACCEPTED)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_remove_friendship_by_addressee(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1253")
    f = _seed_friendship(session, other.id, user.id, FriendshipStatus.ACCEPTED)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_remove_third_party_returns_403(auth_headers, session):
    client, _ = auth_headers
    _, a = _make_user(session, "otheruser1254")
    _, b = _make_user(session, "otheruser1255")
    f = _seed_friendship(session, a.id, b.id, FriendshipStatus.ACCEPTED)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 403


def test_remove_pending_by_requester(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1256")
    f = _seed_friendship(session, user.id, other.id, FriendshipStatus.PENDING)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_remove_pending_by_addressee_returns_409(auth_headers, session):
    client, user = auth_headers
    _, other = _make_user(session, "otheruser1259")
    f = _seed_friendship(session, other.id, user.id, FriendshipStatus.PENDING)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 409


def test_remove_requires_auth(client, session):
    _, a = _make_user(session, "otheruser1257")
    _, b = _make_user(session, "otheruser1258")
    f = _seed_friendship(session, a.id, b.id, FriendshipStatus.ACCEPTED)
    resp = client.delete(f"/friends/{f.id}")
    assert resp.status_code == 401
