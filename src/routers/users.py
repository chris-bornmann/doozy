
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_pagination import Page

from sqlmodel import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate

from db.users import get, get_by_username
from db.main import get_session
from db.models import User, UserNoSecret


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")


router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)


def _fake_decode_token(
    token: str
) -> User:
    return get(1)


async def _get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    user = _fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.enabled:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


@router.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> dict[str, str]:
    user = get_by_username(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not form_data.password == user.password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


def _transform_to_user_no_secret(
    users: List[User]
) -> List[UserNoSecret]:
    return [UserNoSecret(**user.dict()) for user in users]


@router.get("/")
async def read_users(
    *,
    session: Session = Depends(get_session),
) -> Page[UserNoSecret]:
    return paginate(session, select(User), transformer=_transform_to_user_no_secret)


@router.get('/me')
async def read_user_me(
    user: Annotated[UserNoSecret, Depends(_get_current_user)]
) -> User:
    return UserNoSecret(**user.dict())


@router.get("/{id}")
async def read_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    id: int
) -> UserNoSecret:
    user = get(id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserNoSecret(**user.dict())

