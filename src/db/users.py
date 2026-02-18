
from typing import Optional

from sqlmodel import create_engine, Session, select

from db.models import User


def all(
) -> list[User]:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        res = session.exec(select(User))
        return res.all()


def get(
    id: int
) -> Optional[User]:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        user: Optional[User] = session.get(User, id)

    return user


def get_by_username(
    username: str
) -> Optional[User]:
    engine = create_engine('sqlite:///database.db')

    with Session(engine) as session:
        stmt = select(User).where(User.username == username)
        user: Optional[User] = session.exec(stmt).first()

    return user


def remove(
    user: User
) -> None:
    engine = create_engine("sqlite:///database.db")

    with Session(engine) as session:
        session.delete(user)
        session.commit()


def create_user(
    username: str,
    password: str,
    full_name: Optional[str] = None,
) -> User:
    """Create and persist a new user.

    The password is expected to be the _plain_ password; hashing is handled
    here so callers don't have to remember to call ``get_password_hash``.
    """
    from util.security import get_password_hash

    engine = create_engine("sqlite:///database.db")

    user = User(username=username, password=get_password_hash(password))
    if full_name:
        user.full_name = full_name

    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


if __name__ == '__main__':
    print(get(1))
