from typing import Annotated, Optional

import typer
from prettytable import PrettyTable
from sqlmodel import Session

from db.item_orders import move_item
from db.items import all, get as item_get, remove as item_remove
from db.main import engine
from db.models import Item


KEYS = ['id', 'name', 'creator_id']
app = typer.Typer()


@app.command('get')
def get(
    id: Annotated[Optional[int], typer.Argument()] = None
):
    table = PrettyTable()
    table.field_names = KEYS

    with Session(engine) as session:
        if id is None:
            recs = all(session)
        else:
            rec: Optional[Item] = item_get(session, id)
            if rec is None:
                print('No such item')
                raise typer.Exit(code=1)
            recs = [rec]

    data = [[item.model_dump()[key] for key in KEYS] for item in recs]
    table.add_rows(data)
    print(table)


@app.command('remove')
def remove(
    id: Annotated[int, typer.Argument()]
):
    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            print('No such item')
            raise typer.Exit(code=1)

        item_remove(session, item)


@app.command('reorder')
def reorder(
    id: Annotated[int, typer.Argument(help="ID of the item to move")],
    after_id: Annotated[Optional[int], typer.Argument(help="ID of the item to move after, or omit to move to front")] = None,
):
    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            print('No such item')
            raise typer.Exit(code=1)

        if after_id is not None:
            after_item: Optional[Item] = item_get(session, after_id)
            if after_item is None:
                print('No such after_id item')
                raise typer.Exit(code=1)
            if after_item.creator_id != item.creator_id:
                print('Items belong to different users')
                raise typer.Exit(code=1)

        entry = move_item(session, item.creator_id, id, after_id)
        print(f'Item {id} moved, order_key={entry.order_key}')
