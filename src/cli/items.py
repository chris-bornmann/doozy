from typing import Annotated, Optional

import typer
from prettytable import PrettyTable
from sqlmodel import Session

from constants import Priority
from db.item_orders import move_item
from db.items import all, get as item_get, remove as item_remove, update as item_update
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


@app.command('update')
def update(
    id: Annotated[int, typer.Argument(help="ID of the item to update")],
    name:        Annotated[Optional[str],      typer.Option(help="New name")] = None,
    description: Annotated[Optional[str],      typer.Option(help="New description")] = None,
    priority:    Annotated[Optional[Priority], typer.Option(help="New priority")] = None,
    due_on:      Annotated[Optional[str],      typer.Option(help="New due date (ISO 8601, e.g. 2026-04-01T12:00:00Z)")] = None,
):
    """Update one or more fields on an item."""
    changes: dict = {}
    if name        is not None: changes['name']        = name
    if description is not None: changes['description'] = description
    if priority    is not None: changes['priority']    = priority
    if due_on      is not None:
        from datetime import datetime
        changes['due_on'] = datetime.fromisoformat(due_on)

    if not changes:
        print('Nothing to update — supply at least one option.')
        raise typer.Exit(code=1)

    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            print('No such item')
            raise typer.Exit(code=1)
        item_update(session, item, changes)
        print(f'Item {id} updated.')


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
