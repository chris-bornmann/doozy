
import datetime as dt
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from constants import State
from db.models import Item, ItemOwnership, ItemTag, User


def create_item(session: Session, creator_id: int, **kwargs) -> int:
    """
    Create an item and assign ownership to its creator in a single transaction.
    flush() sends the INSERT to get item.id without committing; the
    ItemOwnership row is then added to the same transaction before the
    single commit() call — both rows land atomically.
    """
    item = Item(creator_id=creator_id, **kwargs)
    session.add(item)
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=creator_id))
    session.commit()
    session.refresh(item)
    return item.id


def add(session: Session, item: Item) -> int:
    """Used by CLI interface."""
    session.add(item)
    session.commit()
    session.refresh(item)
    return item.id


def all(session: Session) -> list[Item]:
    return session.exec(select(Item)).all()


def get(session: Session, id: int) -> Optional[Item]:
    return session.get(Item, id)


def find(session: Session, name: str, creator_id: int) -> Optional[Item]:
    stmt = select(Item).where(Item.name == name, Item.creator_id == creator_id)
    return session.exec(stmt).first()


def update(session: Session, item: Item, changes: dict, user_id: Optional[int] = None) -> Item:
    if 'state' in changes:
        if changes['state'] in (State.DONE, State.CANCELLED):
            changes['completed_on'] = dt.datetime.now(dt.timezone.utc)
            changes['completed_by_id'] = user_id
        else:
            changes['completed_on'] = None
            changes['completed_by_id'] = None

    for field, value in changes.items():
        setattr(item, field, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_item(session: Session, item: Item) -> None:
    # Delete an item and all associated tags and ownership records atomically.
    session.exec(sa_delete(ItemTag).where(ItemTag.item_id == item.id))
    session.exec(sa_delete(ItemOwnership).where(ItemOwnership.item_id == item.id))
    session.delete(item)
    session.commit()


def get_ownership(session: Session, item_id: int) -> Optional[ItemOwnership]:
    return session.get(ItemOwnership, item_id)


def get_ownerships_by_ids(session: Session, item_ids: list[int]) -> list[ItemOwnership]:
    return session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id.in_(item_ids))
    ).all()


def get_users_by_ids(session: Session, user_ids: set[int]) -> list[User]:
    return session.exec(select(User).where(User.id.in_(user_ids))).all()


def set_ownership_user(session: Session, ownership: ItemOwnership, user_id: int) -> None:
    ownership.user_id = user_id
    session.add(ownership)
    session.commit()


def set_ownership_group(session: Session, ownership: ItemOwnership, group_id: int) -> None:
    ownership.group_id = group_id
    session.add(ownership)
    session.commit()


def clear_ownership_group(session: Session, ownership: ItemOwnership) -> None:
    ownership.group_id = None
    session.add(ownership)
    session.commit()
