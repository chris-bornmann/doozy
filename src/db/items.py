
import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from constants import State
from db.models import Item


def add(session: Session, item: Item) -> int:
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
