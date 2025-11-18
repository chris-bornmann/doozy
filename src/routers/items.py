
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page
from sqlmodel import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

from app.security import oauth2_scheme
from db.items import add, get, remove
from db.main import get_session
from db.models import Item, User
from routers.forms import Item as FormItem
from routers.users import get_current_user


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


@router.get("/")
async def read_items(
    *,
    session: Session = Depends(get_session),
) -> CustomPage[Item]:
    return paginate(session, select(Item))


@router.get("/{id}")
async def read_item(
    id: int
) -> Item:
    item = get(id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post('/')
async def post_item(
    user: Annotated[User, Depends(get_current_user)],
    data: Annotated[FormItem, Depends()]
) -> dict[str, int]:

    item_id = add(Item(creator_id=user.id, **data.dict()))
    return {'id': item_id}


@router.delete('/{id}')
async def remove_item(
    user: Annotated[User, Depends(get_current_user)],
    id: int
) -> dict[str, bool]:
    item = get(id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")
    remove(item)
    return {'ok': True}
