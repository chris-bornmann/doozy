
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.config import Settings
from app.rate_limit import limiter

_settings = Settings()
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlmodel import Session, select

from app.security import oauth2_scheme
from db.main import get_session
from db.models import ItemTag, Tag, User
from rbac.dependencies import require_permission


router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)

T = TypeVar("T")

CustomPage = CustomizedPage[
    Page[T],
    UseParamsFields(size=Query(10, ge=1, le=1000)),
]


class TagForm(BaseModel):
    name: str = Field(max_length=16, min_length=1)


# TODO
# Tags are global.  That is going to be problematic if there are a lot of
# users creating tags.  Tags could be user or group specific.  If a user-
# specific tag was assigned then it would only show up for users who also
# "owned" that tag.  If a group-specific tag was assigned it would appear
# for anyone in the group.  That leaves a hole because today the creator
# of an item can see their items even if they are no longer the owner or in
# the group.
@router.post('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def create_tag(
    request: Request,
    _: Annotated[User, Depends(require_permission("tags", "write"))],
    data: TagForm,
    session: Session = Depends(get_session),
) -> Tag:
    if session.exec(select(Tag).where(Tag.name == data.name)).first():
        raise HTTPException(status_code=409, detail="Tag already exists")
    tag = Tag(name=data.name)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


@router.get('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_tags(
    request: Request,
    session: Session = Depends(get_session),
    match: Optional[str] = Query(default=None),
) -> CustomPage[Tag]:
    stmt = select(Tag).order_by(Tag.name)
    if match is not None:
        stmt = stmt.where(Tag.name.contains(match))
    return paginate(session, stmt)


# TODO: This allows anyone to delete a tag.  Tags are global, so that's
# not good.  Users should not be able to delete tags used by other people
# because suddenly their items will no longer have the expected tags.
@router.delete('/{id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def delete_tag(
    request: Request,
    _: Annotated[User, Depends(require_permission("tags", "delete"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    tag = session.get(Tag, id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    session.exec(delete(ItemTag).where(ItemTag.tag_id == id))
    session.delete(tag)
    session.commit()
    return {'ok': True}
