
from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import get_settings
from constants import UserState
from db import users as db_users
from db.models import Item, User
from db.users import get_by_username
from db.verification import create_verification
from rbac.roles import assign_role
from schemas import UserForm
from util.security import get_password_hash


_settings = get_settings()


def list_users_stmt():
    """Statement for paginating all users."""
    return select(User)


def get_user(session: Session, user_id: int) -> User:
    """Fetch a user by ID. Raises 404 if not found."""
    user = db_users.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_items_stmt(user_id: int):
    """Statement for paginating items created by a user."""
    return select(Item).where(Item.creator_id == user_id)


async def create_user(session: Session, data: UserForm) -> User:
    """Create a new user with default role and send a verification email."""
    from services.verification import send_verification_email

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
    assign_role(session, user.id, "user")

    raw_token = create_verification(session, user.id, _settings.VERIFICATION_EXPIRE_MINUTES)
    try:
        await send_verification_email(user, raw_token)
    except Exception:
        pass  # email failure is non-fatal; user can request a resend later

    return user
