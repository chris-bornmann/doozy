
import datetime as dt
from enum import Enum
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_pagination import Page
from sqlalchemy import and_, asc, delete, desc, nulls_last, nullsfirst
from sqlmodel import Session, select
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

import sqlalchemy as sa

from app.security import oauth2_scheme
from constants import FriendshipStatus
from db import friendships as db_friends
from db import groups as db_groups
from db.item_orders import move_item
from db.items import add, create_item, get, remove, update
from db.main import get_session
from db.models import GroupMember, Item, ItemOwnership, ItemTag, Tag, User, UserItemOrder
from db.users import get_by_username
from rbac.dependencies import require_permission
from routers.forms import Item as FormItem, ItemFilter, ItemRead, PatchItem, Reorder


class SortBy(str, Enum):
    priority   = "priority"
    created_on = "created_on"
    due_on     = "due_on"
    state      = "state"
    custom     = "custom"


router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)


T = TypeVar("T")


CustomPage = CustomizedPage[
    Page[T],
    UseParamsFields(
        size=Query(2, ge=1, le=1000),
    ),
]


_SORT_COLUMNS = {
    SortBy.priority:   Item.priority,
    SortBy.created_on: Item.created_on,
    SortBy.due_on:     Item.due_on,
    SortBy.state:      Item.state,
}


def _owned_by(user_id: int):
    """Base select(Item) for items accessible to user_id via direct ownership, group membership, or creation."""
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
    # Also include items the user created, even if ownership was later transferred
    return select(Item).where(
        sa.or_(
            Item.id.in_(accessible),
            Item.creator_id == user_id,
        )
    )


def _get_ownership(session: Session, item_id: int) -> ItemOwnership:
    """Return the ItemOwnership row for item_id. Raises 404 if missing."""
    ownership = session.get(ItemOwnership, item_id)
    if ownership is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return ownership


def _can_see(session: Session, user_id: int, item: Item, ownership: ItemOwnership) -> bool:
    """Return True if user is the owner, the creator, or a member of the item's group."""
    if ownership.user_id == user_id:
        return True
    if item.creator_id == user_id:
        return True
    if ownership.group_id is not None:
        return db_groups.get_member(session, ownership.group_id, user_id) is not None
    return False


def _to_item_reads(session: Session, items: list[Item]) -> list[ItemRead]:
    """
    Convert a list of Item DB rows into ItemRead response objects.
    Uses two bulk queries (ownership rows + owner usernames) instead of
    one query per item, so page size doesn't affect query count.
    """
    if not items:
        return []

    item_ids = [item.id for item in items]

    ownerships = session.exec(
        select(ItemOwnership).where(ItemOwnership.item_id.in_(item_ids))
    ).all()
    ownership_by_item = {o.item_id: o for o in ownerships}

    owner_ids = {o.user_id for o in ownerships if o.user_id is not None}
    if owner_ids:
        owner_users = session.exec(select(User).where(User.id.in_(owner_ids))).all()
        username_by_id = {u.id: u.username for u in owner_users}
    else:
        username_by_id = {}

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


@router.get("/")
async def read_items(
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
) -> CustomPage[ItemRead]:
    if sort_by == SortBy.custom:
        col = UserItemOrder.order_key
        order_expr = desc(col) if reverse else asc(col)
        stmt = (
            _owned_by(user.id)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user.id),
            )
            .order_by(order_expr)
        )
    else:
        col = _SORT_COLUMNS[sort_by]
        order_expr = nullsfirst(desc(col)) if reverse else nulls_last(asc(col))
        stmt = _owned_by(user.id).order_by(order_expr)
    return paginate(session, stmt, transformer=lambda items: _to_item_reads(session, items))


def _apply_filters(stmt, f: ItemFilter):
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


@router.post('/search')
async def search_items(
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
    filter: ItemFilter,
) -> CustomPage[ItemRead]:
    if sort_by == SortBy.custom:
        col = UserItemOrder.order_key
        order_expr = desc(col) if reverse else asc(col)
        stmt = (
            _owned_by(user.id)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user.id),
            )
            .order_by(order_expr)
        )
    else:
        col = _SORT_COLUMNS[sort_by]
        order_expr = nullsfirst(desc(col)) if reverse else nulls_last(asc(col))
        stmt = _owned_by(user.id).order_by(order_expr)
    return paginate(session, _apply_filters(stmt, filter), transformer=lambda items: _to_item_reads(session, items))


@router.options('/search')
async def options_items_search() -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.get("/{id}")
async def read_item(
    user: Annotated[User, Depends(require_permission("items", "read"))],
    id: int,
    session: Session = Depends(get_session),
) -> ItemRead:
    item: Item | None = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if not _can_see(session, user.id, item, ownership):
        raise HTTPException(status_code=403, detail="Access denied")
    return _to_item_reads(session, [item])[0]


@router.post('/')
async def post_item(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    data: Annotated[FormItem, Depends()],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    item_id = create_item(session, creator_id=user.id, **data.model_dump())
    return {'id': item_id}


@router.patch('/{id}')
async def patch_item(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    data: PatchItem,
    session: Session = Depends(get_session),
) -> ItemRead:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this item")
    updated = update(session, item, data.model_dump(include=data.model_fields_set), user_id=user.id)
    return _to_item_reads(session, [updated])[0]


@router.post('/{id}/reorder')
async def reorder_item(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    data: Reorder,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if not _can_see(session, user.id, item, ownership):
        raise HTTPException(status_code=403, detail="Access denied")

    if data.after_id is not None:
        after_item = get(session, data.after_id)
        if after_item is None:
            raise HTTPException(status_code=404, detail="after_id item not found")
        after_ownership = _get_ownership(session, data.after_id)
        if not _can_see(session, user.id, after_item, after_ownership):
            raise HTTPException(status_code=403, detail="after_id item not visible to user")

    entry = move_item(session, user.id, id, data.after_id)
    return {'order_key': entry.order_key}


@router.post('/{id}/assign/user/{username}')
async def assign_to_user(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    username: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can transfer ownership")
    target = get_by_username(session, username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Friendship required unless transferring to self
    if target.id != user.id:
        friendship = db_friends.get_between(session, user.id, target.id)
        if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=403, detail="You can only transfer ownership to a friend")
    # If the item is in a group, the new owner must be a member of that group
    if ownership.group_id is not None:
        if db_groups.get_member(session, ownership.group_id, target.id) is None:
            raise HTTPException(status_code=403, detail="New owner must be a member of the item's group")
    ownership.user_id = target.id
    # group_id is intentionally left unchanged
    session.add(ownership)
    session.commit()
    return {"ok": True}


@router.post('/{id}/assign/group/{group_id}')
async def assign_to_group(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    group_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can assign a group")
    group = db_groups.get(session, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if db_groups.get_member(session, group_id, user.id) is None:
        raise HTTPException(status_code=403, detail="You are not a member of that group")
    ownership.group_id = group_id
    # user_id is intentionally left unchanged
    session.add(ownership)
    session.commit()
    return {"ok": True}


@router.delete('/{id}/assign/group')
async def unassign_group(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can unassign the group")
    ownership.group_id = None
    session.add(ownership)
    session.commit()
    return {"ok": True}


@router.options('/{id}/assign/user/{username}')
async def options_assign_user(id: int, username: str) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.options('/{id}/assign/group/{group_id}')
async def options_assign_group(id: int, group_id: int) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.options('/{id}/assign/group')
async def options_unassign_group(id: int) -> Response:
    return Response(headers={"Allow": "DELETE, OPTIONS"}, status_code=204)


@router.options('/')
async def options_items() -> Response:
    return Response(headers={"Allow": "GET, POST, OPTIONS"}, status_code=204)


@router.options('/{id}')
async def options_item(id: int) -> Response:
    return Response(headers={"Allow": "GET, PATCH, DELETE, OPTIONS"}, status_code=204)


@router.options('/{id}/reorder')
async def options_item_reorder(id: int) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.delete('/{id}')
async def remove_item(
    user: Annotated[User, Depends(require_permission("items", "delete"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    ownership = _get_ownership(session, id)
    if ownership.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this item")
    session.exec(delete(ItemTag).where(ItemTag.item_id == id))
    session.exec(delete(ItemOwnership).where(ItemOwnership.item_id == id))
    remove(session, item)
    return {'ok': True}
