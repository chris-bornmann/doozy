
import datetime
from typing import Optional

from sqlalchemy.engine import Engine  # Just to set the type.
from sqlmodel import create_engine, Session, SQLModel

from db.models import Item, Priority, User


def _create_users(
    engine: Engine
) -> None:
    user_1 = User(username='chris.bornmann@pobox.com', password='1111111111', full_name='Chris Bornmann')
    user_2 = User(username='john.smith@pobox.com', password='2222222222')
    user_3 = User(username='mary.sue@pobox.com', password='3333333333', enabled=False)

    with Session(engine) as session:
        session.add(user_1)
        session.add(user_2)
        session.add(user_3)
        session.commit()

        return [user_1, user_2, user_3]


def create():
    engine = create_engine("sqlite:///database.db")
    
    SQLModel.metadata.create_all(engine)

    users = _create_users(engine)

    item_1 = Item(name='abc 1111111111', description='hi', creator=users[0])
    item_2 = Item(name='def 2222222222', creator=users[0])
    item_3 = Item(name='ghi 3333333333', creator=users[1], due_on=datetime.datetime.now(datetime.timezone.utc))
    item_4 = Item(name='jkl 4444444444', creator=users[2], priority=Priority.LOW)
    
    with Session(engine) as session:
        session.add(item_1)
        session.add(item_2)
        session.add(item_3)
        session.add(item_4)
        session.commit()

    with Session(engine) as session:
        item_2: Optional[Item] = session.get(Item, 2)
        if item_2 is not None:
            print(item_2)
            item_2.description = "my description"
            session.add(item_2)
            session.commit()
            print(item_2)
            session.refresh(item_2)
            print(item_2)

    with Session(engine) as session:
        item_3: Optional[Item] = session.get(Item, 3)
        if item_3 is not None:
            print(item_3)
            item_3.due_on = datetime.datetime.now(datetime.timezone.utc)
            session.add(item_3)
            session.commit()
            print(item_3)
            session.refresh(item_3)
            print(item_3)


if __name__ == '__main__':
    create()
