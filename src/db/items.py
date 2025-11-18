
from typing import Optional

from sqlmodel import create_engine, Session, select

from db.models import Item


def add(
    item: Item,
) -> int:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        session.add(item)
        session.commit()
        return item.id


def all(
) -> list[Item]:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        res = session.exec(select(Item))
        return res.all()


def get(
    id: int
) -> Optional[Item]:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        item: Optional[Item] = session.get(Item, id)

    return item


def remove(
    item: Item
) -> None:
    engine = create_engine("sqlite:///database.db")
    
    with Session(engine) as session:
        session.delete(item)
        session.commit()


if __name__ == '__main__':
    print(get(1))
