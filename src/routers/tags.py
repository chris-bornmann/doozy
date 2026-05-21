
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, Query, Request
from app.config import get_settings
from app.rate_limit import limiter
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import Tag, User
from rbac.dependencies import require_permission
import services.tags as tag_service


_settings = get_settings()

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
    return tag_service.create_tag(session, user, data.name)


@router.get('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_tags(
    request: Request,
    _: Annotated[User, Depends(require_permission("item_tags", "read"))],
    session: Session = Depends(get_session),
    match: Optional[str] = Query(default=None),
) -> CustomPage[Tag]:
    return paginate(session, tag_service.list_tags_stmt(match))


@router.delete('/{id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def delete_tag(
    request: Request,
    user: Annotated[User, Depends(require_permission("item_tags", "delete"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    tag_service.delete_tag(session, user, id)
    return {'ok': True}
