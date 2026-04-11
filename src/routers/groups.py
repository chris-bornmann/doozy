
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.security import oauth2_scheme
from constants import FriendshipStatus
from db import friendships as db_friends
from db import groups as db
from db.main import get_session
from db.models import Group, User
from db.users import get as get_user, get_by_username
from rbac.dependencies import require_permission
from routers.forms import GroupRead


router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)


class GroupCreate(BaseModel):
    name: str = Field(max_length=64, min_length=1)


def _to_read(session: Session, group: Group) -> GroupRead:
    owner = get_user(session, group.owner_id)
    group_members = db.members(session, group.id)
    return GroupRead(
        id=group.id,
        name=group.name,
        owner=owner.username,
        members=[u.username for u in group_members],
        created_on=group.created_on,
    )


def _get_or_404(session: Session, group_id: int) -> Group:
    group = db.get(session, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.post("/", status_code=201)
async def create_group(
    data: GroupCreate,
    user: Annotated[User, Depends(require_permission("groups", "write"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    try:
        group = db.create(session, name=data.name, owner_id=user.id)
    except Exception:
        raise HTTPException(status_code=409, detail="A group with that name already exists")
    return _to_read(session, group)


@router.get("/")
async def list_groups(
    user: Annotated[User, Depends(require_permission("groups", "read"))],
    session: Session = Depends(get_session),
) -> Page[GroupRead]:
    return paginate(
        session,
        db.my_groups_stmt(user.id),
        transformer=lambda rows: [_to_read(session, g) for g in rows],
    )


@router.get("/{id}")
async def get_group(
    id: int,
    user: Annotated[User, Depends(require_permission("groups", "read"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    group = _get_or_404(session, id)
    if db.get_member(session, id, user.id) is None:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return _to_read(session, group)


@router.delete("/{id}")
async def delete_group(
    id: int,
    user: Annotated[User, Depends(require_permission("groups", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    group = _get_or_404(session, id)
    if group.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a group")
    db.delete(session, group)
    return {"ok": True}


@router.post("/{id}/members/{username}")
async def add_member(
    id: int,
    username: str,
    user: Annotated[User, Depends(require_permission("groups", "write"))],
    session: Session = Depends(get_session),
) -> GroupRead:
    group = _get_or_404(session, id)
    if group.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can add members")
    target = get_by_username(session, username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get_member(session, id, target.id) is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this group")
    friendship = db_friends.get_between(session, user.id, target.id)
    if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(status_code=403, detail="You can only add friends to a group")
    db.add_member(session, id, target.id)
    return _to_read(session, group)


@router.delete("/{id}/members/{username}")
async def remove_member(
    id: int,
    username: str,
    user: Annotated[User, Depends(require_permission("groups", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    group = _get_or_404(session, id)
    if group.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can remove members")
    target = get_by_username(session, username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == group.owner_id:
        raise HTTPException(status_code=409, detail="The owner cannot be removed from their own group")
    gm = db.get_member(session, id, target.id)
    if gm is None:
        raise HTTPException(status_code=404, detail="User is not a member of this group")
    db.remove_member(session, gm)
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
