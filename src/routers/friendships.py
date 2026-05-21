
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from app.config import get_settings
from app.rate_limit import limiter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import UserNoSecret
from rbac.dependencies import require_permission
from db.models import User
from schemas import FriendshipRead
import services.friendships as friendship_service


_settings = get_settings()

router = APIRouter(
    prefix="/friends",
    tags=["friendships"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)


# TODO: Add additional responses for all the status codes (400, 409, etc).
@router.post("/request/{username}", status_code=201)
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def request_friendship(
    request: Request,
    username: str,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    return friendship_service.request_friendship(session, user, username)


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_friends(
    request: Request,
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[UserNoSecret]:
    return paginate(
        session,
        friendship_service.list_friends_stmt(user.id),
        transformer=lambda users: [UserNoSecret(**u.model_dump()) for u in users],
    )


@router.get("/pending")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_pending(
    request: Request,
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[FriendshipRead]:
    return paginate(
        session,
        friendship_service.list_pending_stmt(user.id),
        transformer=lambda rows: [friendship_service.enrich_friendship(session, r) for r in rows],
    )


@router.get("/sent")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_sent(
    request: Request,
    user: Annotated[User, Depends(require_permission("friendships", "read"))],
    session: Session = Depends(get_session),
) -> Page[FriendshipRead]:
    return paginate(
        session,
        friendship_service.list_sent_stmt(user.id),
        transformer=lambda rows: [friendship_service.enrich_friendship(session, r) for r in rows],
    )


@router.post("/{id}/accept")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def accept_friendship(
    request: Request,
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    return friendship_service.accept_friendship(session, user, id)


@router.post("/{id}/decline")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def decline_friendship(
    request: Request,
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "write"))],
    session: Session = Depends(get_session),
) -> FriendshipRead:
    return friendship_service.decline_friendship(session, user, id)


@router.delete("/{id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_friendship(
    request: Request,
    id: int,
    user: Annotated[User, Depends(require_permission("friendships", "delete"))],
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    friendship_service.remove_friendship(session, user, id)
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
