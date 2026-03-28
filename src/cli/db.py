import datetime
from typing import Optional

import typer
from sqlmodel import Session, SQLModel

from db.main import engine
from db.models import Item, Priority, User
from util.security import get_password_hash


app = typer.Typer()


def _create_users(session: Session) -> list[User]:
    user_1 = User(username='chris.bornmann@pobox.com', password=get_password_hash('1111111111'), full_name='Chris Bornmann')
    user_2 = User(username='john.smith@pobox.com', password=get_password_hash('2222222222'))
    user_3 = User(username='mary.sue@pobox.com', password=get_password_hash('3333333333'), enabled=False)

    session.add(user_1)
    session.add(user_2)
    session.add(user_3)
    session.commit()

    return [user_1, user_2, user_3]


def _create_items(session: Session, users: list[User]) -> None:
    item_1 = Item(name='abc 1111111111', description='hi', creator_id=users[0].id, priority=Priority.LOW)
    item_2 = Item(name='def 2222222222', creator_id=users[0].id, priority=Priority.HIGH)
    item_3 = Item(name='ghi 3333333333', creator_id=users[1].id, due_on=datetime.datetime.now(datetime.timezone.utc))
    item_4 = Item(name='jkl 4444444444', creator_id=users[2].id, priority=Priority.LOW)

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


@app.command('create')
def create(
    seed: bool = typer.Option(False, '--seed', help='Populate the database with sample data after creating it.'),
):
    """Create database tables."""
    SQLModel.metadata.create_all(engine)
    print('Database tables created.')

    if seed:
        with Session(engine) as session:
            users = _create_users(session)
            _create_items(session, users)
        print('Sample data inserted.')
