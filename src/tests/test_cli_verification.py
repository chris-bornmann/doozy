import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch

from cli.verification import app
from db.models import User, UserVerification
from db.verification import create_verification


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded_user(db_engine):
    """Insert a test user and return it."""
    with Session(db_engine) as session:
        user = User(
            username="sendtest1",
            password="hashed_password_here",
            full_name="Send Test",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@pytest.fixture
def runner(db_engine):
    with patch("cli.verification.engine", db_engine):
        yield CliRunner(), db_engine


# ---------------------------------------------------------------------------
# verify send — success path
# ---------------------------------------------------------------------------

def test_send_success(runner, seeded_user):
    cli, engine = runner
    with patch("cli.verification.send_verification_email", new=AsyncMock()) as mock_send:
        result = cli.invoke(app, [seeded_user.username])
    assert result.exit_code == 0
    assert "sent" in result.output.lower()
    mock_send.assert_called_once()


def test_send_creates_verification_record(runner, seeded_user, db_engine):
    cli, engine = runner
    with patch("cli.verification.send_verification_email", new=AsyncMock()):
        cli.invoke(app, [seeded_user.username])
    with Session(db_engine) as session:
        record = session.exec(
            __import__("sqlmodel").select(UserVerification)
            .where(UserVerification.user_id == seeded_user.id)
        ).first()
    assert record is not None
    assert record.used is False


def test_send_passes_user_to_email_function(runner, seeded_user, db_engine):
    cli, _ = runner
    with patch("cli.verification.send_verification_email", new=AsyncMock()) as mock_send:
        cli.invoke(app, [seeded_user.username])
    assert mock_send.call_count == 1
    # Confirm the verification record was created for the expected user.
    # (Accessing mock call args directly raises DetachedInstanceError since
    # the CLI session is already closed when invoke() returns.)
    from sqlmodel import select as sm_select
    with Session(db_engine) as s:
        record = s.exec(
            sm_select(UserVerification).where(UserVerification.user_id == seeded_user.id)
        ).first()
    assert record is not None


# ---------------------------------------------------------------------------
# verify send — error paths
# ---------------------------------------------------------------------------

def test_send_user_not_found(runner):
    cli, _ = runner
    result = cli.invoke(app, ["nobody@nowhere.com"])
    assert result.exit_code == 1
    assert "no user found" in result.output.lower()


def test_send_smtp_failure_exits_nonzero(runner, seeded_user):
    cli, _ = runner
    with patch(
        "cli.verification.send_verification_email",
        new=AsyncMock(side_effect=Exception("SMTP error")),
    ):
        result = cli.invoke(app, [seeded_user.username])
    assert result.exit_code == 1
    assert "failed" in result.output.lower()


def test_send_smtp_failure_does_not_suppress_error_message(runner, seeded_user):
    cli, _ = runner
    with patch(
        "cli.verification.send_verification_email",
        new=AsyncMock(side_effect=Exception("connection refused")),
    ):
        result = cli.invoke(app, [seeded_user.username])
    assert "connection refused" in result.output
