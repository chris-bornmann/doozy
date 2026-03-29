import os
import sys

# app/main.py does `from middleware import …` — middleware lives in src/app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

# Must be set before any app imports so Settings() initialises cleanly.
os.environ.setdefault('SECRET_KEY', 'testsecretkey1234567890abcdef1234')
os.environ.setdefault('ALGORITHM', 'HS256')
os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('GOOGLE_CLIENT_ID', 'fakeid')
os.environ.setdefault('GOOGLE_CLIENT_SECRET', 'fakesecret')

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from db.main import get_session
from db.users import create_user
from util.security import encode_token


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Unauthenticated test client."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(session: Session):
    """Returns (TestClient, User) with a valid JWT in the default headers."""
    user = create_user(session, username="testuser1", password="password1234")
    token = encode_token({"sub": user.username})
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(
        app,
        raise_server_exceptions=True,
        headers={"Authorization": f"Bearer {token}"},
    )
    yield client, user
    app.dependency_overrides.clear()
