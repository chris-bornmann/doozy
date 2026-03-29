
from enum import Enum
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page
from sqlalchemy import and_
from sqlmodel import Session, select
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

from app.security import oauth2_scheme
from db.item_orders import move_item
from db.items import add, get, remove, update
from db.main import get_session
from db.models import Item, User, UserItemOrder
from routers.forms import Item as FormItem, PatchItem, Reorder
from routers.users import get_current_user


class SortBy(str, Enum):
    priority   = "priority"
    created_on = "created_on"
    due_on     = "due_on"
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
}


@router.get("/")
async def read_items(
    *,
    user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
) -> CustomPage[Item]:
    if sort_by == SortBy.custom:
        stmt = (
            select(Item)
            .outerjoin(
                UserItemOrder,
                and_(UserItemOrder.item_id == Item.id, UserItemOrder.user_id == user.id),
            )
            .where(Item.creator_id == user.id)
            .order_by(UserItemOrder.order_key)
        )
    else:
        stmt = (
            select(Item)
            .where(Item.creator_id == user.id)
            .order_by(_SORT_COLUMNS[sort_by])
        )
    return paginate(session, stmt)


@router.get("/{id}")
async def read_item(
    user: Annotated[User, Depends(get_current_user)],
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
    user: Annotated[User, Depends(get_current_user)],
    data: Annotated[FormItem, Depends()],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    item_id = add(session, Item(creator_id=user.id, **data.model_dump()))
    return {'id': item_id}


@router.patch('/{id}')
async def patch_item(
    user: Annotated[User, Depends(get_current_user)],
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
    user: Annotated[User, Depends(get_current_user)],
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


@router.delete('/{id}')
async def remove_item(
    user: Annotated[User, Depends(get_current_user)],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = get(session, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")
    remove(session, item)
    return {'ok': True}
