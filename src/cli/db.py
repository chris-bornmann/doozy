import datetime
import random
import string
from typing import Optional

import typer
from sqlmodel import Session, SQLModel

from db.main import engine
from db.models import Item, Priority, State, User
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


_ADJECTIVES = [
    "quick", "lazy", "bright", "dark", "loud", "silent", "smooth", "rough",
    "ancient", "modern", "frozen", "burning", "broken", "shiny", "dusty",
    "hidden", "open", "closed", "empty", "full",
]

_NOUNS = [
    "report", "meeting", "deadline", "invoice", "review", "update", "audit",
    "proposal", "ticket", "release", "deployment", "migration", "refactor",
    "demo", "sprint", "backlog", "hotfix", "feature", "document", "sketch",
]

_DESCRIPTIONS = [
    "Needs urgent attention",
    "Low risk, can wait",
    "Blocked by external dependency",
    "Waiting for sign-off",
    "In review with stakeholders",
    "Ready to start",
    "Requires further investigation",
    "Part of Q2 objectives",
    "Customer-facing impact",
    "Internal tooling improvement",
    "Follow up from last meeting",
    "Automate this process",
    "Reduce technical debt",
    "Improve test coverage",
    "Performance optimisation",
    None,
]


def _random_name() -> str:
    """Generate a random item name between 8 and 32 characters."""
    adj  = random.choice(_ADJECTIVES)
    noun = random.choice(_NOUNS)
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"{adj} {noun} {suffix}"[:32]


def _random_due_on() -> Optional[datetime.datetime]:
    """Return a random datetime, past or future, or None."""
    if random.random() < 0.15:          # ~15% have no due date
        return None
    offset_days = random.randint(-180, 180)
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=offset_days)


@app.command('blitz')
def blitz(
    count: int = typer.Option(100, '--count', help='Number of items to create.'),
    creator_id: int = typer.Option(1, '--creator-id', help='ID of the user to assign items to.'),
):
    """Populate the database with random items."""
    priorities = list(Priority)
    states     = list(State)

    with Session(engine) as session:
        for _ in range(count):
            session.add(Item(
                name=_random_name(),
                description=random.choice(_DESCRIPTIONS),
                priority=random.choice(priorities),
                state=random.choice(states),
                due_on=_random_due_on(),
                creator_id=creator_id,
            ))
        session.commit()

    typer.echo(f"{count} items added for creator_id={creator_id}.")


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
