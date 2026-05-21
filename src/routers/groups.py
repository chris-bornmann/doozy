
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from app.config import get_settings
from app.rate_limit import limiter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import User
from rbac.dependencies import require_permission
from schemas import GroupRead
import services.groups as group_service


_settings = get_settings()

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)


class GroupCreate(BaseModel):
    name: str = Field(max_length=64, min_length=1)


# TODO: Need a solution for duplicate groups names amongst unrelated parties.
@router.post("/", status_code=201)
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def create_group(
    request: Request,
    data: GroupCreate,
    user: Annotated[User, Depends(require_permission("groups", "write"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    return group_service.create_group(session, user, data.name)


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_groups(
    request: Request,
    user: Annotated[User, Depends(require_permission("groups", "read"))],
    session: Session = Depends(get_session),
) -> Page[GroupRead]:
    return paginate(
        session,
        group_service.list_groups_stmt(user.id),
        transformer=lambda rows: [group_service.enrich_group(session, g) for g in rows],
    )


@router.get("/{id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def get_group(
    request: Request,
    id: int,
    user: Annotated[User, Depends(require_permission("groups", "read"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    return group_service.get_group(session, user, id)


@router.delete("/{id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def delete_group(
    request: Request,
    id: int,
    user: Annotated[User, Depends(require_permission("groups", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    group_service.delete_group(session, user, id)
    return {"ok": True}


# TODO: Terminology confusion.  We have item creators and item owners, but with
# groups we call the creators owners and don't have the concept of an owner.  I
# need to update the terminology to only use "creator" for groups.
@router.post("/{id}/members/{username}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def add_member(
    request: Request,
    id: int,
    username: str,
    user: Annotated[User, Depends(require_permission("groups", "write"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    return group_service.add_member(session, user, id, username)


@router.delete("/{id}/members/{username}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_member(
    request: Request,
    id: int,
    username: str,
    user: Annotated[User, Depends(require_permission("groups", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    group_service.remove_member(session, user, id, username)
    return {"ok": True}


@router.options("/")
async def options_groups() -> Response:
    return Response(headers={"Allow": "GET, POST, OPTIONS"}, status_code=204)


@router.options("/{id}")
async def options_group(id: int) -> Response:
    return Response(headers={"Allow": "GET, DELETE, OPTIONS"}, status_code=204)


@router.options("/{id}/members/{username}")
async def options_group_members(id: int, username: str) -> Response:
    return Response(headers={"Allow": "POST, DELETE, OPTIONS"}, status_code=204)
