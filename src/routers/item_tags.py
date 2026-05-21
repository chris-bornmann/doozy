
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from app.config import get_settings
from app.rate_limit import limiter
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import Item, ItemTag, Tag, User
from rbac.dependencies import require_permission
import services.item_tags as item_tag_service


class LookupBy(str, Enum):
    item = "item"
    tag  = "tag"


class ItemTagForm(BaseModel):
    item_id: int
    tag_id: int


_settings = get_settings()


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
        stmt = item_tag_service.get_tags_for_item(session, user, id)
        return paginate(session, stmt, params=params)
    else:
        stmt = item_tag_service.get_items_for_tag(session, user, id)
        return paginate(session, stmt, params=params)


@router.post("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def assign_tag(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "write"))],
    data: ItemTagForm,
    session: Session = Depends(get_session),
) -> ItemTag:
    return item_tag_service.assign_tag(session, user, data.item_id, data.tag_id)


@router.delete("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_tag_assignment(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "delete"))],
    data: ItemTagForm,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item_tag_service.remove_tag_assignment(session, user, data.item_id, data.tag_id)
    return {"ok": True}
