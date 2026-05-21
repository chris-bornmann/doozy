
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.rate_limit import limiter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from sqlmodel import Session

from app.config import get_settings
from app.security import oauth2_scheme
from db.main import get_session
from db.models import Item, User, UserNoSecret
from rbac.dependencies import require_permission
from schemas import UserForm
from util.security import get_current_user
import services.users as user_service


_settings = get_settings()


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)

# Public router — no auth required (e.g. registration)
public_router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={409: {"description": "Conflict"}},
)


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.enabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_users(
    request: Request,
    *,
    user: User = Depends(require_permission("users", "read")),
    session: Session = Depends(get_session),
) -> Page[UserNoSecret]:
    return paginate(session, user_service.list_users_stmt(),
                    transformer=lambda users: [UserNoSecret(**u.model_dump()) for u in users])


@public_router.get('/me')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_user_me(
    request: Request,
    user: Annotated[UserNoSecret, Depends(get_current_active_user)],
) -> UserNoSecret:
    return UserNoSecret(**user.model_dump())


@router.get("/{id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_user(
    request: Request,
    id: int,
    current_user: User = Depends(require_permission("users", "read")),
    session: Session = Depends(get_session),
) -> UserNoSecret:
    target = user_service.get_user(session, id)
    return UserNoSecret(**target.model_dump())


@public_router.post('/')
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def create_user(
    request: Request,
    data: UserForm,
    session: Session = Depends(get_session),
) -> UserNoSecret:
    user = await user_service.create_user(session, data)
    return UserNoSecret(**user.model_dump())


@router.get('/{id}/items')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_user_items(
    request: Request,
    id: int,
    current_user: User = Depends(require_permission("users", "read")),
    session: Session = Depends(get_session),
) -> Page[Item]:
    return paginate(session, user_service.get_user_items_stmt(id))


@router.options('/')
async def options_users() -> Response:
    return Response(headers={"Allow": "GET, POST, OPTIONS"}, status_code=204)


@router.options('/me')
async def options_user_me() -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)


@router.options('/{id}')
async def options_user(id: int) -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)


@router.options('/{id}/items')
async def options_user_items(id: int) -> Response:
    return Response(headers={"Allow": "GET, OPTIONS"}, status_code=204)
