
from typing import Optional

from sqlmodel import Session, select

from db.models import ItemTag


def get(session: Session, item_id: int, tag_id: int) -> Optional[ItemTag]:
    return session.exec(
        select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag_id)
    ).first()


def add(session: Session, item_id: int, tag_id: int) -> ItemTag:
    entry = ItemTag(item_id=item_id, tag_id=tag_id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def remove(session: Session, entry: ItemTag) -> None:
    session.delete(entry)
    session.commit()


def by_item(session: Session, item_id: int) -> list[ItemTag]:
    return session.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all()
