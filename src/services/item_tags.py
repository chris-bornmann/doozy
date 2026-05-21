
from sqlmodel import Session, select

from db import item_tags as db_item_tags
from db import items as db_items
from db import tags as db_tags
from db.models import Item, ItemTag, Tag, User
from exceptions import DoozyConflictError, DoozyForbiddenError, DoozyNotFoundError
from services.items import can_see, get_item, get_items_stmt


def get_tags_for_item(session: Session, user: User, item_id: int):
    """Return a paginate-ready statement for tags on a given item. User must be able to see the item."""
    get_item(session, user, item_id)
    return (
        select(Tag)
        .join(ItemTag, ItemTag.tag_id == Tag.id)
        .where(ItemTag.item_id == item_id)
        .order_by(Tag.name)
    )


def get_items_for_tag(session: Session, user: User, tag_id: int):
    """Return a paginate-ready statement for items that have a given tag, filtered to what user can see."""
    if db_tags.get(session, tag_id) is None:
        raise DoozyNotFoundError("Tag not found")
    return (
        get_items_stmt(user.id)
        .join(ItemTag, ItemTag.item_id == Item.id)
        .where(ItemTag.tag_id == tag_id)
        .order_by(Item.name)
    )


def assign_tag(session: Session, user: User, item_id: int, tag_id: int) -> ItemTag:
    """Assign a tag to an item. Only the item creator may do this."""
    item = db_items.get(session, item_id)
    if item is None:
        raise DoozyNotFoundError("Item not found")
    if item.creator_id != user.id:
        raise DoozyForbiddenError("Not the creator")
    if db_tags.get(session, tag_id) is None:
        raise DoozyNotFoundError("Tag not found")
    if db_item_tags.get(session, item_id, tag_id) is not None:
        raise DoozyConflictError("Tag already assigned to item")
    return db_item_tags.add(session, item_id, tag_id)


def remove_tag_assignment(session: Session, user: User, item_id: int, tag_id: int) -> None:
    """Remove a tag assignment. Only the item creator may do this."""
    item = db_items.get(session, item_id)
    if item is None:
        raise DoozyNotFoundError("Item not found")
    if item.creator_id != user.id:
        raise DoozyForbiddenError("Not the creator")
    entry = db_item_tags.get(session, item_id, tag_id)
    if entry is None:
        raise DoozyNotFoundError("Assignment not found")
    db_item_tags.remove(session, entry)
