
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


def remove(session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()
