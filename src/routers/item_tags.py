
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.config import Settings
from app.rate_limit import limiter

_settings = Settings()
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlmodel import Session, select

from app.security import oauth2_scheme
from db.main import get_session
from db.models import Item, ItemTag, Tag, User
from rbac.dependencies import require_permission
from routers.items import _can_see, _get_ownership, _owned_by


class LookupBy(str, Enum):
    item = "item"
    tag  = "tag"


class ItemTagForm(BaseModel):
    item_id: int
    tag_id: int


router = APIRouter(
    prefix="/item_tags",
    tags=["item_tags"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)


# The "..." in the Query means that the argument is required.  There is no
# default and something must be provided.  The Query itself represents
# parameters that follow the "?" on a URL.
@router.get("/", response_model=None)
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_item_tags(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "read"))],
    by: LookupBy = Query(..., description="'item' to get tags for an item; 'tag' to get items for a tag"),
    id: int = Query(..., description="ID of the item or tag, depending on 'by'"),
    session: Session = Depends(get_session),
    params: Params = Depends(),
) -> Page[Tag] | Page[Item]:
    # TODO: This should probably be two helper functions.
    if by == LookupBy.item:
        item = session.get(Item, id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        ownership = _get_ownership(session, id)
        if not _can_see(session, user.id, item, ownership):
            raise HTTPException(status_code=403, detail="Access denied")
        stmt = (
            select(Tag)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == id)
            .order_by(Tag.name)
        )
        return paginate(session, stmt, params=params)
    else:
        tag = session.get(Tag, id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        # Return only items visible to the user, using the same criteria as the items endpoints.
        stmt = (
            _owned_by(user.id)
            .join(ItemTag, ItemTag.item_id == Item.id)
            .where(ItemTag.tag_id == id)
            .order_by(Item.name)
        )
        return paginate(session, stmt, params=params)


@router.post("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def assign_tag(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "write"))],
    data: ItemTagForm,
    session: Session = Depends(get_session),
) -> ItemTag:
    item = session.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")

    if session.get(Tag, data.tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = session.exec(
        select(ItemTag)
        .where(ItemTag.item_id == data.item_id)
        .where(ItemTag.tag_id == data.tag_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tag already assigned to item")

    entry = ItemTag(item_id=data.item_id, tag_id=data.tag_id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_tag_assignment(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "delete"))],
    data: ItemTagForm,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item = session.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not the creator")

    entry = session.exec(
        select(ItemTag)
        .where(ItemTag.item_id == data.item_id)
        .where(ItemTag.tag_id == data.tag_id)
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    session.delete(entry)
    session.commit()
    return {"ok": True}
