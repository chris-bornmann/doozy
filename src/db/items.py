
from typing import Optional

from sqlmodel import Session, select

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


def find(session: Session, name: str) -> Optional[Item]:
    stmt = select(Item).where(Item.name == name)
    return session.exec(stmt).first()


def update(session: Session, item: Item, changes: dict) -> Item:
    for field, value in changes.items():
        setattr(item, field, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def remove(session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()
