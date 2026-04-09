
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_pagination import Page

from sqlmodel import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate

from app.config import Settings
from app.security import oauth2_scheme
from constants import UserState
from db.main import get_session
from db.models import Item, User, UserNoSecret
from db.users import get, get_by_username
from db.verification import create_verification
from routers.forms import User as UserForm
from routers.verification import send_verification_email
from util.security import decode_token, get_password_hash


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


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
) -> User:
    data = decode_token(token)
    if data.get('error'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid authentication credentials: {data['error']}',
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = data.get('sub')
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials: missing sub",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_by_username(session, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.enabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.get("/")
async def read_users(
    *,
    session: Session = Depends(get_session),
) -> Page[UserNoSecret]:
    return paginate(session, select(User),
                    transformer=lambda users: [UserNoSecret(**u.model_dump()) for u in users])


@router.get('/me')
async def read_user_me(
    user: Annotated[UserNoSecret, Depends(get_current_active_user)]
) -> UserNoSecret:
    return UserNoSecret(**user.model_dump())


@router.get("/{id}")
async def read_user(
    id: int,
    session: Session = Depends(get_session),
) -> UserNoSecret:
    user = get(session, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserNoSecret(**user.model_dump())


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


@public_router.post('/')
async def create_user(
    data: UserForm,
    session: Session = Depends(get_session),
) -> UserNoSecret:
    if get_by_username(session, data.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=data.username,
        full_name=data.full_name,
        password=get_password_hash(data.password),
        state=UserState.NEW,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    settings = Settings()
    raw_token = create_verification(session, user.id, settings.VERIFICATION_EXPIRE_MINUTES)
    try:
        await send_verification_email(user, raw_token)
    except Exception:
        pass  # email failure is non-fatal; user can request a resend later

    return UserNoSecret(**user.model_dump())


@router.get('/{id}/items')
async def read_user_items(
    id: int,
    session: Session = Depends(get_session)
) -> Page[Item]:
    return paginate(session, select(Item).where(Item.creator_id == id))
