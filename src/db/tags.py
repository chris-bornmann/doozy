
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from db.models import ItemTag, Tag


def get(session: Session, id: int) -> Optional[Tag]:
    return session.get(Tag, id)


def get_by_name(session: Session, name: str) -> Optional[Tag]:
    return session.exec(select(Tag).where(Tag.name == name)).first()


def create(session: Session, name: str, creator_id: int) -> Tag:
    tag = Tag(name=name, creator_id=creator_id)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def is_assigned(session: Session, tag_id: int) -> bool:
    return session.exec(select(ItemTag).where(ItemTag.tag_id == tag_id)).first() is not None


def delete(session: Session, tag: Tag) -> None:
    """Delete a tag and all its item assignments atomically."""
    session.exec(sa_delete(ItemTag).where(ItemTag.tag_id == tag.id))
    session.delete(tag)
    session.commit()
