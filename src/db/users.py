
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


if __name__ == '__main__':
    print(get(1))
