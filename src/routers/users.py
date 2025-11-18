
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_pagination import Page

from sqlmodel import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate

from app.security import oauth2_scheme
from db.main import get_session
from db.models import Item, User, UserNoSecret
from db.users import get, get_by_username


"""
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")
"""


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)


# !@# It seems like this, and get_current_user should be with the /token
# endpoint, which currently lives in src/app/main.py.  I don't like it
# there, but that would be better than here.
def _fake_decode_token(
    token: str
) -> User:
    return get(1)


async def get_current_user(
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


"""
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
"""


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
    user: Annotated[UserNoSecret, Depends(get_current_user)]
) -> UserNoSecret:
    return UserNoSecret(**user.dict())


@router.get("/{id}")
async def read_user(
    id: int
) -> UserNoSecret:
    user = get(id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserNoSecret(**user.dict())


@router.get('/{id}/items')
async def read_user_items(
    id: int,
    session: Session = Depends(get_session)
) -> Page[Item]:
    breakpoint()

    return paginate(session, select(Item).where(Item.creator_id == id))
