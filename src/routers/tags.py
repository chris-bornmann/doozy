
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.config import get_settings
from app.rate_limit import limiter

_settings = get_settings()
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlmodel import Session, select

from app.security import oauth2_scheme
from db.main import get_session
from db.models import ItemTag, Tag, User
from rbac.dependencies import get_user_roles, require_permission
from rbac.enforcer import get_enforcer


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


@router.post('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def create_tag(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "write"))],
    data: TagForm,
    session: Session = Depends(get_session),
) -> Tag:
    if session.exec(select(Tag).where(Tag.name == data.name)).first():
        raise HTTPException(status_code=409, detail="Tag already exists")
    tag = Tag(name=data.name, creator_id=user.id)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


@router.get('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_tags(
    request: Request,
    _: Annotated[User, Depends(require_permission("item_tags", "read"))],
    session: Session = Depends(get_session),
    match: Optional[str] = Query(default=None),
) -> CustomPage[Tag]:
    stmt = select(Tag).order_by(Tag.name)
    if match is not None:
        stmt = stmt.where(Tag.name.contains(match))
    return paginate(session, stmt)


@router.delete('/{id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def delete_tag(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "delete"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    tag = session.get(Tag, id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    roles = get_user_roles(session, user.id)
    enforcer = get_enforcer()
    is_admin = any(enforcer.enforce(role, "item_tags", "xxx") for role in roles)

    if is_admin:
        # Admins can delete any tag; remove all item assignments first.
        session.exec(delete(ItemTag).where(ItemTag.tag_id == id))
    else:
        if tag.creator_id != user.id:
            raise HTTPException(status_code=403, detail="You can only delete tags you created")
        if session.exec(select(ItemTag).where(ItemTag.tag_id == id)).first():
            raise HTTPException(status_code=403, detail="Tag is assigned to one or more work items")

    session.delete(tag)
    session.commit()
    return {'ok': True}
