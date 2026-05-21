import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner
from unittest.mock import patch

from cli.tags import app
from db.models import Tag


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
def runner(db_engine):
    """Yields (CliRunner, db_engine, creator_id) with a test user pre-seeded."""
    from db.models import User
    with Session(db_engine) as session:
        user = User(username="clitagsuser1", password="hashed1234")
        session.add(user)
        session.commit()
        session.refresh(user)
        creator_id = user.id
    with patch("cli.tags.engine", db_engine):
        yield CliRunner(), db_engine, creator_id


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_tag(runner):
    cli, engine, creator_id = runner
    result = cli.invoke(app, ["add", "backend", "--creator-id", str(creator_id)])
    assert result.exit_code == 0
    assert "backend" in result.output

    with Session(engine) as session:
        assert session.exec(
            __import__("sqlmodel").select(Tag).where(Tag.name == "backend")
        ).first() is not None


def test_add_tag_duplicate(runner):
    cli, _, creator_id = runner
    cli.invoke(app, ["add", "backend", "--creator-id", str(creator_id)])
    result = cli.invoke(app, ["add", "backend", "--creator-id", str(creator_id)])
    assert result.exit_code == 1
    assert "already exists" in result.output


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_tags_empty(runner):
    cli, _, _id = runner
    result = cli.invoke(app, ["get"])
    assert result.exit_code == 0


def test_get_tags_lists_all(runner):
    cli, _, creator_id = runner
    cli.invoke(app, ["add", "alpha", "--creator-id", str(creator_id)])
    cli.invoke(app, ["add", "beta", "--creator-id", str(creator_id)])
    result = cli.invoke(app, ["get"])
    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" in result.output


def test_get_tags_alphabetical(runner):
    cli, _, creator_id = runner
    for name in ["zebra", "apple", "mango"]:
        cli.invoke(app, ["add", name, "--creator-id", str(creator_id)])
    result = cli.invoke(app, ["get"])
    positions = {name: result.output.index(name) for name in ["zebra", "apple", "mango"]}
    assert positions["apple"] < positions["mango"] < positions["zebra"]


def test_get_tags_match(runner):
    cli, _, creator_id = runner
    cli.invoke(app, ["add", "frontend", "--creator-id", str(creator_id)])
    cli.invoke(app, ["add", "backend", "--creator-id", str(creator_id)])
    cli.invoke(app, ["add", "python", "--creator-id", str(creator_id)])
    result = cli.invoke(app, ["get", "--match", "end"])
    assert "frontend" in result.output
    assert "backend" in result.output
    assert "python" not in result.output


def test_get_tags_match_no_results(runner):
    cli, _, creator_id = runner
    cli.invoke(app, ["add", "python", "--creator-id", str(creator_id)])
    result = cli.invoke(app, ["get", "--match", "java"])
    assert result.exit_code == 0
    assert "python" not in result.output


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_tag(runner):
    cli, engine, creator_id = runner
    cli.invoke(app, ["add", "removeme", "--creator-id", str(creator_id)])
    with Session(engine) as session:
        tag = session.exec(__import__("sqlmodel").select(Tag).where(Tag.name == "removeme")).first()
    result = cli.invoke(app, ["delete", str(tag.id)])
    assert result.exit_code == 0
    assert "removeme" in result.output


def test_delete_tag_not_found(runner):
    cli, _, _id = runner
    result = cli.invoke(app, ["delete", "9999"])
    assert result.exit_code == 1
    assert "no tag" in result.output.lower()
