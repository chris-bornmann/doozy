
import datetime as dt
from enum import Enum
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_pagination import Page
from sqlalchemy import and_, asc, delete, desc, nulls_last, nullsfirst
from sqlmodel import Session, select
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

from app.security import oauth2_scheme
from db.item_orders import move_item
from db.items import add, get, remove, update
from db.main import get_session
from db.models import Item, ItemTag, Tag, User, UserItemOrder
from rbac.dependencies import require_permission
from routers.forms import Item as FormItem, ItemFilter, PatchItem, Reorder


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


@router.get("/")
async def read_items(
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
) -> CustomPage[Item]:
    if sort_by == SortBy.custom:
        col = UserItemOrder.order_key
        order_expr = desc(col) if reverse else asc(col)
        stmt = (
            select(Item)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user.id),
            )
            .where(Item.creator_id == user.id)
            .order_by(order_expr)
        )
    else:
        col = _SORT_COLUMNS[sort_by]
        order_expr = nullsfirst(desc(col)) if reverse else nulls_last(asc(col))
        stmt = (
            select(Item)
            .where(Item.creator_id == user.id)
            .order_by(order_expr)
        )
    return paginate(session, stmt)


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

    return stmt


@router.post('/search')
async def search_items(
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
    filter: ItemFilter,
) -> CustomPage[Item]:
    if sort_by == SortBy.custom:
        col = UserItemOrder.order_key
        order_expr = desc(col) if reverse else asc(col)
        stmt = (
            select(Item)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user.id),
            )
            .where(Item.creator_id == user.id)
            .order_by(order_expr)
        )
    else:
        col = _SORT_COLUMNS[sort_by]
        order_expr = nullsfirst(desc(col)) if reverse else nulls_last(asc(col))
        stmt = (
            select(Item)
            .where(Item.creator_id == user.id)
            .order_by(order_expr)
        )
    return paginate(session, _apply_filters(stmt, filter))


@router.options('/search')
async def options_items_search() -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.get("/{id}")
async def read_item(
    user: Annotated[User, Depends(require_permission("items", "read"))],
    id: int,
    session: Session = Depends(get_session),
) -> Item:
    item: Item | None = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")
    return item


@router.post('/')
async def post_item(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    data: Annotated[FormItem, Depends()],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    item_id = add(session, Item(creator_id=user.id, **data.model_dump()))
    return {'id': item_id}


@router.patch('/{id}')
async def patch_item(
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    data: PatchItem,
    session: Session = Depends(get_session),
) -> Item:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")
    return update(session, item, data.model_dump(include=data.model_fields_set))


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
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")

    if data.after_id is not None:
        after_item = get(session, data.after_id)
        if after_item is None:
            raise HTTPException(status_code=404, detail="after_id item not found")
        if after_item.creator_id != user.id:
            raise HTTPException(status_code=403, detail="after_id item not owned by user")

    entry = move_item(session, user.id, id, data.after_id)
    return {'order_key': entry.order_key}


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
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")
    session.exec(delete(ItemTag).where(ItemTag.item_id == id))
    remove(session, item)
    return {'ok': True}
