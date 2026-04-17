
import pytest
from sqlmodel import select

from db.items import create_item
from db.models import ItemOwnership
from db.users import create_user


def test_create_item_returns_id(session):
    user = create_user(session, "alice", "password1234")
    item_id = create_item(session, user.id, name="Buy milk")
    assert isinstance(item_id, int)


def test_create_item_creates_ownership_record(session):
    # create_item must write an ItemOwnership row so the item is visible to its creator.
    user = create_user(session, "alice", "password1234")
    item_id = create_item(session, user.id, name="Buy milk")

    ownership = session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id == item_id)
    ).first()

    assert ownership is not None
    assert ownership.user_id == user.id


def test_create_item_ownership_scoped_to_creator(session):
    # Ownership row must belong to the creator, not another user.
    alice = create_user(session, "alice", "password1234")
    bob = create_user(session, "bob", "password1234")
    item_id = create_item(session, alice.id, name="Alice's task")

    ownership = session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id == item_id)
    ).first()

    assert ownership.user_id == alice.id
    assert ownership.user_id != bob.id


def test_create_item_each_item_gets_own_ownership_record(session):
    # Each item created must have exactly one corresponding ownership record.
    user = create_user(session, "alice", "password1234")
    id_a = create_item(session, user.id, name="Task A")
    id_b = create_item(session, user.id, name="Task B")

    ownership_a = session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id == id_a)
    ).first()
    ownership_b = session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id == id_b)
    ).first()

    assert ownership_a is not None
    assert ownership_b is not None
    assert ownership_a.item_id != ownership_b.item_id
