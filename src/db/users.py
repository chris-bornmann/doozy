
from typing import Optional

from sqlmodel import Session, select

from db.models import User


def all(session: Session) -> list[User]:
    return session.exec(select(User)).all()


def get(session: Session, id: int) -> Optional[User]:
    return session.get(User, id)


def get_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()


def remove(session: Session, user: User) -> None:
    session.delete(user)
    session.commit()


# Named create_user (not add) because it encapsulates password hashing —
# a different abstraction level from the simple add() in db/items.py.
def create_user(
    session: Session,
    username: str,
    password: str,
    full_name: Optional[str] = None,
) -> User:
    """Create and persist a new user.

    The password is expected to be the _plain_ password; hashing is handled
    here so callers don't have to remember to call ``get_password_hash``.
    """
    from util.security import get_password_hash

    user = User(username=username, password=get_password_hash(password))
    if full_name:
        user.full_name = full_name

    session.add(user)
    session.commit()
    session.refresh(user)
    return user
