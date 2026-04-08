import datetime as dt
from unittest.mock import AsyncMock, patch

from constants import UserState
from db.models import User, UserVerification
from db.users import create_user
from db.verification import create_verification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session, username="verifyuser1", password="password1234") -> User:
    return create_user(session, username=username, password=password)


# ---------------------------------------------------------------------------
# GET /verify/?token=…  — valid token
# ---------------------------------------------------------------------------

def test_valid_token_redirects_to_login(client, session):
    user = _make_user(session)
    raw_token = create_verification(session, user.id)
    response = client.get("/verify/", params={"token": raw_token}, follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "login" in response.headers["location"]


def test_valid_token_sets_user_state_to_authenticated(client, session):
    user = _make_user(session)
    raw_token = create_verification(session, user.id)
    client.get("/verify/", params={"token": raw_token})
    session.refresh(user)
    assert user.state == UserState.AUTHENTICATED


def test_valid_token_is_marked_used(client, session):
    user = _make_user(session)
    raw_token = create_verification(session, user.id)
    client.get("/verify/", params={"token": raw_token})
    record = session.exec(
        __import__("sqlmodel").select(UserVerification)
        .where(UserVerification.user_id == user.id)
    ).first()
    assert record.used is True


# ---------------------------------------------------------------------------
# GET /verify/?token=…  — invalid / expired / reused token
# ---------------------------------------------------------------------------

def test_invalid_token_returns_400(client, session):
    _make_user(session)
    assert client.get("/verify/", params={"token": "notarealtoken"}).status_code == 400


def test_expired_token_returns_400(client, session):
    user = _make_user(session)
    raw_token = create_verification(session, user.id, expire_minutes=-1)
    assert client.get("/verify/", params={"token": raw_token}).status_code == 400


def test_reused_token_returns_400(client, session):
    user = _make_user(session)
    raw_token = create_verification(session, user.id)
    client.get("/verify/", params={"token": raw_token})
    assert client.get("/verify/", params={"token": raw_token}).status_code == 400


def test_missing_token_param_returns_422(client):
    assert client.get("/verify/").status_code == 422
