
from typing import Optional

from sqlmodel import create_engine, Session, select

from db.models import Item


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


if __name__ == '__main__':
    print(get(1))
