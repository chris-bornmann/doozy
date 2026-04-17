
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import Friendship, UserNoSecret
from db import friendships as db
from db.users import get as get_user, get_by_username
from rbac.dependencies import require_permission
from db.models import User
from constants import FriendshipStatus
from routers.forms import FriendshipRead


router = APIRouter(
    prefix="/friends",
    tags=["friendships"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)


def _to_read(session: Session, friendship: Friendship) -> FriendshipRead:
    """Build a FriendshipRead with resolved usernames (no IDs exposed)."""
    requester = get_user(session, friendship.requester_id)
    addressee = get_user(session, friendship.addressee_id)
    return FriendshipRead(
        id=friendship.id,
        requester=requester.username,
        addressee=addressee.username,
        status=friendship.status,
        created_on=friendship.created_on,
        updated_on=friendship.updated_on,
    )


def _get_or_404(session: Session, friendship_id: int):
    f = db.get(session, friendship_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Friendship not found")
    return f


# TODO: Add additional responses for all the status codes (400, 409, etc).
@router.post("/request/{username}", status_code=201)
async def request_friendship(
    username: str,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    if username == user.username:
        raise HTTPException(status_code=400, detail="Cannot send a friend request to yourself")
    target = get_by_username(session, username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        friendship = db.request(session, user.id, target.id)
    except ValueError:
        raise HTTPException(status_code=409, detail="Friend request already exists")
    return _to_read(session, friendship)


@router.get("/")
async def list_friends(
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[UserNoSecret]:
    return paginate(
        session,
        db.friends_stmt(user.id),
        transformer=lambda users: [UserNoSecret(**u.model_dump()) for u in users],
    )


@router.get("/pending")
async def list_pending(
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[FriendshipRead]:
    return paginate(
        session,
        db.pending_received_stmt(user.id),
        transformer=lambda rows: [_to_read(session, r) for r in rows],
    )


@router.get("/sent")
async def list_sent(
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[FriendshipRead]:
    return paginate(
        session,
        db.sent_stmt(user.id),
        transformer=lambda rows: [_to_read(session, r) for r in rows],
    )


@router.post("/{id}/accept")
async def accept_friendship(
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    friendship = _get_or_404(session, id)
    if friendship.addressee_id != user.id:
        raise HTTPException(status_code=403, detail="Only the recipient can accept a friend request")
    if friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=409, detail="Friend request is not pending")
    friendship = db.accept(session, friendship)
    return _to_read(session, friendship)


@router.post("/{id}/decline")
async def decline_friendship(
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    friendship = _get_or_404(session, id)
    if friendship.addressee_id != user.id:
        raise HTTPException(status_code=403, detail="Only the recipient can decline a friend request")
    if friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=409, detail="Friend request is not pending")
    friendship = db.decline(session, friendship)
    return _to_read(session, friendship)


@router.delete("/{id}")
async def remove_friendship(
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    friendship = _get_or_404(session, id)
    if user.id not in (friendship.requester_id, friendship.addressee_id):
        raise HTTPException(status_code=403, detail="Not a party to this friendship")
    can_remove = (
        friendship.status == FriendshipStatus.ACCEPTED
        or (friendship.status == FriendshipStatus.PENDING and friendship.requester_id == user.id)
    )
    if not can_remove:
        raise HTTPException(status_code=409, detail="Cannot remove this friendship")
    db.remove(session, friendship)
    return {"ok": True}


@router.options("/")
async def options_friends() -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)


@router.options("/pending")
async def options_pending() -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)


@router.options("/sent")
async def options_sent() -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)


@router.options("/{id}")
async def options_friendship(id: int) -> Response:
    return Response(headers={"Allow": "POST, DELETE, OPTIONS"}, status_code=204)
