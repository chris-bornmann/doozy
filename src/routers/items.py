
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page
from sqlmodel import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields

from db.items import get
from db.main import get_session
from db.models import Item


router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "Not found"}},
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
