
from sqlmodel import Session, select

from app.config import get_settings
from db import users as db_users
from db.models import Item, User
from db.users import get_by_username
from db.verification import create_verification
from exceptions import DoozyConflictError
from schemas import UserForm


_settings = get_settings()


def list_users_stmt():
    """Statement for paginating all users."""
    return select(User)


def get_user(session: Session, user_id: int) -> User:
    """Fetch a user by ID. Raises 404 if not found."""
    from exceptions import DoozyNotFoundError
    user = db_users.get(session, user_id)
    if user is None:
        raise DoozyNotFoundError("User not found")
    return user


def get_user_items_stmt(user_id: int):
    """Statement for paginating items created by a user."""
    return select(Item).where(Item.creator_id == user_id)


async def create_user(session: Session, data: UserForm) -> User:
    """Create a new user with default role and send a verification email."""
    from services.verification import send_verification_email

    if get_by_username(session, data.username):
        raise DoozyConflictError("Username already exists")

    user = db_users.create_user(session, data.username, data.password, data.full_name)

    raw_token = create_verification(session, user.id, _settings.VERIFICATION_EXPIRE_MINUTES)
    await send_verification_email(user, raw_token)

    return user
