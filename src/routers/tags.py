
from typing import Annotated, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlmodel import Session, select

from app.security import oauth2_scheme
from db.main import get_session
from db.models import ItemTag, Tag
from routers.users import get_current_user


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
async def create_tag(
    _: Annotated[object, Depends(get_current_user)],
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
async def list_tags(
    session: Session = Depends(get_session),
    match: Optional[str] = Query(default=None),
) -> CustomPage[Tag]:
    stmt = select(Tag).order_by(Tag.name)
    if match is not None:
        stmt = stmt.where(Tag.name.contains(match))
    return paginate(session, stmt)


@router.delete('/{id}')
async def delete_tag(
    _: Annotated[object, Depends(get_current_user)],
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
