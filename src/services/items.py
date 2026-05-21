import datetime as dt
from typing import Optional

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import asc, desc, nulls_last, nullsfirst, and_
from sqlmodel import Session, select

from constants import FriendshipStatus
from db import friendships as db_friends
from db import groups as db_groups
from db import items as db_items
from db.item_orders import move_item
from db.models import GroupMember, Item, ItemOwnership, ItemTag, Tag, User, UserItemOrder
from db.users import get_by_username
from schemas import ItemFilter, ItemRead


_SORT_COLUMNS = {
    "priority":   Item.priority,
    "created_on": Item.created_on,
    "due_on":     Item.due_on,
    "state":      Item.state,
}


def get_items_stmt(user_id: int):
    """SELECT for items visible to user_id via ownership, group membership, or creation."""
    my_groups = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    accessible = (
        select(ItemOwnership.item_id)
        .where(
            sa.or_(
                ItemOwnership.user_id == user_id,
                ItemOwnership.group_id.in_(my_groups),
            )
        )
    )
    return select(Item).where(
        sa.or_(
            Item.id.in_(accessible),
            Item.creator_id == user_id,
        )
    )


def get_sorted_items_stmt(user_id: int, sort_by: str, reverse: bool):
    """Build a paginate-ready statement with sorting applied."""
    if sort_by == "custom":
        col = UserItemOrder.order_key
        order_expr = desc(col) if reverse else asc(col)
        return (
            get_items_stmt(user_id)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user_id),
            )
            .order_by(order_expr)
        )
    else:
        col = _SORT_COLUMNS[sort_by]
        order_expr = nullsfirst(desc(col)) if reverse else nulls_last(asc(col))
        return get_items_stmt(user_id).order_by(order_expr)


def can_see(session: Session, user_id: int, item: Item, ownership: ItemOwnership) -> bool:
    """Return True if user is the owner, the creator, or a member of the item's group."""
    if ownership.user_id == user_id:
        return True
    if item.creator_id == user_id:
        return True
    if ownership.group_id is not None:
        return db_groups.get_member(session, ownership.group_id, user_id) is not None
    return False


def get_item(session: Session, user: User, item_id: int) -> tuple[Item, ItemOwnership]:
    """Fetch an item and verify the user can see it. Raises 404/403 if not."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if not can_see(session, user.id, item, ownership):
        raise HTTPException(status_code=403, detail="Access denied")
    return item, ownership


def enrich_items(session: Session, items: list[Item]) -> list[ItemRead]:
    """
    Convert Item rows to ItemRead response objects.
    Uses two bulk queries (ownership rows + owner usernames) instead of
    one query per item, so page size doesn't affect query count.
    """
    if not items:
        return []
    item_ids = [item.id for item in items]
    ownerships = db_items.get_ownerships_by_ids(session, item_ids)
    assert len(ownerships) == len(item_ids)
    ownership_by_item = {o.item_id: o for o in ownerships}
    owner_ids = {o.user_id for o in ownerships if o.user_id is not None}
    assert owner_ids
    owner_users = db_items.get_users_by_ids(session, owner_ids)
    username_by_id = {u.id: u.username for u in owner_users}
    result = []
    for item in items:
        ownership = ownership_by_item.get(item.id)
        owner_username = username_by_id.get(ownership.user_id, "") if ownership else ""
        group_id = ownership.group_id if ownership else None
        result.append(ItemRead(
            id=item.id,
            name=item.name,
            description=item.description,
            priority=item.priority,
            state=item.state,
            creator_id=item.creator_id,
            created_on=item.created_on,
            due_on=item.due_on,
            completed_on=item.completed_on,
            completed_by_id=item.completed_by_id,
            updated_on=item.updated_on,
            owner=owner_username,
            group_id=group_id,
        ))
    return result


def apply_filters(stmt, f: ItemFilter):
    """Apply search filters to an existing item query statement."""
    if f.name:
        stmt = stmt.where(Item.name.ilike(f'%{f.name}%'))
    if f.state:
        stmt = stmt.where(Item.state.in_(f.state))
    if f.priority:
        stmt = stmt.where(Item.priority.in_(f.priority))

    for col, after, before, on in [
        (Item.created_on,   f.created_after,   f.created_before,   f.created_on),
        (Item.due_on,       f.due_after,        f.due_before,       f.due_on),
        (Item.completed_on, f.completed_after,  f.completed_before, f.completed_on),
    ]:
        if on:
            start = dt.datetime(on.year, on.month, on.day, tzinfo=dt.timezone.utc)
            stmt = stmt.where(col >= start).where(col < start + dt.timedelta(days=1))
        if after:
            stmt = stmt.where(col > after)
        if before:
            stmt = stmt.where(col < before)

    if f.tags:
        tag_subq = (
            select(ItemTag.item_id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Tag.name.in_(f.tags))
            .subquery()
        )
        stmt = stmt.where(Item.id.in_(select(tag_subq.c.item_id)))

    if f.group_ids:
        group_item_subq = select(ItemOwnership.item_id).where(
            ItemOwnership.group_id.in_(f.group_ids)
        )
        stmt = stmt.where(Item.id.in_(group_item_subq))

    return stmt


def create_item(session: Session, user: User, data) -> int:
    """Create a new item owned by user. Returns the new item ID."""
    return db_items.create_item(session, creator_id=user.id, **data.model_dump())


def update_item(session: Session, user: User, item_id: int, changes: dict) -> ItemRead:
    """Update an item. Only the owner may modify."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this item")
    updated = db_items.update(session, item, changes, user_id=user.id)
    return enrich_items(session, [updated])[0]


def delete_item(session: Session, user: User, item_id: int) -> None:
    """Delete an item. Only the owner may delete."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this item")
    db_items.delete_item(session, item)


def reorder_item(session: Session, user: User, item_id: int, after_id: Optional[int]):
    """Reorder an item. User must be able to see both the item and the after_id item."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or not can_see(session, user.id, item, ownership):
        raise HTTPException(status_code=403, detail="Access denied")

    if after_id is not None:
        after_item = db_items.get(session, after_id)
        if after_item is None:
            raise HTTPException(status_code=404, detail="after_id item not found")
        after_ownership = db_items.get_ownership(session, after_id)
        if after_ownership is None or not can_see(session, user.id, after_item, after_ownership):
            raise HTTPException(status_code=403, detail="after_id item not visible to user")

    return move_item(session, user.id, item_id, after_id)


def assign_to_user(session: Session, user: User, item_id: int, username: str) -> None:
    """Transfer item ownership to another user. Must be friends unless transferring to self."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can transfer ownership")
    target = get_by_username(session, username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id != user.id:
        friendship = db_friends.get_between(session, user.id, target.id)
        if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=403, detail="You can only transfer ownership to a friend")

    if ownership.group_id is not None:
        if db_groups.get_member(session, ownership.group_id, target.id) is None:
            raise HTTPException(status_code=403, detail="New owner must be a member of the item's group")

    db_items.set_ownership_user(session, ownership, target.id)


def assign_to_group(session: Session, user: User, item_id: int, group_id: int) -> None:
    """Assign an item to a group. User must be the owner and a group member."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can assign a group")
    group = db_groups.get(session, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if db_groups.get_member(session, group_id, user.id) is None:
        raise HTTPException(status_code=403, detail="You are not a member of that group")
    db_items.set_ownership_group(session, ownership, group_id)


def unassign_group(session: Session, user: User, item_id: int) -> None:
    """Remove a group assignment from an item. User must be the owner."""
    item = db_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = db_items.get_ownership(session, item_id)
    if ownership is None or ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can unassign the group")
    db_items.clear_ownership_group(session, ownership)
