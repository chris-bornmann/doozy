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
    with patch("cli.tags.engine", db_engine):
        yield CliRunner(), db_engine


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_tag(runner):
    cli, engine = runner
    result = cli.invoke(app, ["add", "backend"])
    assert result.exit_code == 0
    assert "backend" in result.output

    with Session(engine) as session:
        assert session.exec(
            __import__("sqlmodel").select(Tag).where(Tag.name == "backend")
        ).first() is not None


def test_add_tag_duplicate(runner):
    cli, _ = runner
    cli.invoke(app, ["add", "backend"])
    result = cli.invoke(app, ["add", "backend"])
    assert result.exit_code == 1
    assert "already exists" in result.output


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_tags_empty(runner):
    cli, _ = runner
    result = cli.invoke(app, ["get"])
    assert result.exit_code == 0


def test_get_tags_lists_all(runner):
    cli, _ = runner
    cli.invoke(app, ["add", "alpha"])
    cli.invoke(app, ["add", "beta"])
    result = cli.invoke(app, ["get"])
    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" in result.output


def test_get_tags_alphabetical(runner):
    cli, _ = runner
    for name in ["zebra", "apple", "mango"]:
        cli.invoke(app, ["add", name])
    result = cli.invoke(app, ["get"])
    positions = {name: result.output.index(name) for name in ["zebra", "apple", "mango"]}
    assert positions["apple"] < positions["mango"] < positions["zebra"]


def test_get_tags_match(runner):
    cli, _ = runner
    cli.invoke(app, ["add", "frontend"])
    cli.invoke(app, ["add", "backend"])
    cli.invoke(app, ["add", "python"])
    result = cli.invoke(app, ["get", "--match", "end"])
    assert "frontend" in result.output
    assert "backend" in result.output
    assert "python" not in result.output


def test_get_tags_match_no_results(runner):
    cli, _ = runner
    cli.invoke(app, ["add", "python"])
    result = cli.invoke(app, ["get", "--match", "java"])
    assert result.exit_code == 0
    assert "python" not in result.output


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_tag(runner):
    cli, engine = runner
    cli.invoke(app, ["add", "removeme"])
    with Session(engine) as session:
        tag = session.exec(__import__("sqlmodel").select(Tag).where(Tag.name == "removeme")).first()
    result = cli.invoke(app, ["delete", str(tag.id)])
    assert result.exit_code == 0
    assert "removeme" in result.output


def test_delete_tag_not_found(runner):
    cli, _ = runner
    result = cli.invoke(app, ["delete", "9999"])
    assert result.exit_code == 1
    assert "no tag" in result.output.lower()
