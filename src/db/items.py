
import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from constants import State
from db.models import Item, ItemOwnership


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


def remove(session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()
