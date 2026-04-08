import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner
from unittest.mock import patch

from cli.item_tags import app
from db.models import Item, ItemTag, Tag


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
    with patch("cli.item_tags.engine", db_engine):
        yield CliRunner(), db_engine


@pytest.fixture
def seeded(db_engine):
    """Return (item, tag) pre-seeded into the test database."""
    from db.models import User
    with Session(db_engine) as session:
        user = User(username="cliuser11", password="hashed1234", full_name="CLI User")
        session.add(user)
        session.commit()
        session.refresh(user)

        item = Item(name="CLI test item aa", creator_id=user.id)
        tag  = Tag(name="clitag")
        session.add_all([item, tag])
        session.commit()
        session.refresh(item)
        session.refresh(tag)
    return item, tag


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_assignment(runner, seeded):
    cli, engine = runner
    item, tag = seeded
    result = cli.invoke(app, ["add", str(item.id), str(tag.id)])
    assert result.exit_code == 0
    with Session(engine) as session:
        entry = session.exec(
            select(ItemTag)
            .where(ItemTag.item_id == item.id)
            .where(ItemTag.tag_id  == tag.id)
        ).first()
        assert entry is not None


def test_add_assignment_duplicate(runner, seeded):
    cli, _ = runner
    item, tag = seeded
    cli.invoke(app, ["add", str(item.id), str(tag.id)])
    result = cli.invoke(app, ["add", str(item.id), str(tag.id)])
    assert result.exit_code == 1
    assert "already assigned" in result.output


def test_add_assignment_item_not_found(runner, seeded):
    cli, _ = runner
    _, tag = seeded
    result = cli.invoke(app, ["add", "9999", str(tag.id)])
    assert result.exit_code == 1
    assert "no item" in result.output.lower()


def test_add_assignment_tag_not_found(runner, seeded):
    cli, _ = runner
    item, _ = seeded
    result = cli.invoke(app, ["add", str(item.id), "9999"])
    assert result.exit_code == 1
    assert "no tag" in result.output.lower()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_assignment(runner, seeded, db_engine):
    cli, engine = runner
    item, tag = seeded
    with Session(engine) as session:
        session.add(ItemTag(item_id=item.id, tag_id=tag.id))
        session.commit()
    result = cli.invoke(app, ["delete", str(item.id), str(tag.id)])
    assert result.exit_code == 0
    with Session(engine) as session:
        assert session.exec(
            select(ItemTag)
            .where(ItemTag.item_id == item.id)
            .where(ItemTag.tag_id  == tag.id)
        ).first() is None


def test_delete_assignment_not_found(runner, seeded):
    cli, _ = runner
    item, tag = seeded
    result = cli.invoke(app, ["delete", str(item.id), str(tag.id)])
    assert result.exit_code == 1
    assert "no such assignment" in result.output.lower()


# ---------------------------------------------------------------------------
# items (list items for a tag)
# ---------------------------------------------------------------------------

def test_list_items_for_tag(runner, seeded, db_engine):
    cli, engine = runner
    item, tag = seeded
    with Session(engine) as session:
        session.add(ItemTag(item_id=item.id, tag_id=tag.id))
        session.commit()
    result = cli.invoke(app, ["items", str(tag.id)])
    assert result.exit_code == 0
    assert "CLI test item aa" in result.output


def test_list_items_for_tag_not_found(runner):
    cli, _ = runner
    result = cli.invoke(app, ["items", "9999"])
    assert result.exit_code == 1
    assert "no tag" in result.output.lower()


# ---------------------------------------------------------------------------
# tags (list tags for an item)
# ---------------------------------------------------------------------------

def test_list_tags_for_item(runner, seeded, db_engine):
    cli, engine = runner
    item, tag = seeded
    with Session(engine) as session:
        session.add(ItemTag(item_id=item.id, tag_id=tag.id))
        session.commit()
    result = cli.invoke(app, ["tags", str(item.id)])
    assert result.exit_code == 0
    assert "clitag" in result.output


def test_list_tags_for_item_not_found(runner):
    cli, _ = runner
    result = cli.invoke(app, ["tags", "9999"])
    assert result.exit_code == 1
    assert "no item" in result.output.lower()
