from datetime import datetime
from typing import Annotated, Optional

import typer
from prettytable import PrettyTable
from sqlmodel import Session

from constants import Priority
from db.item_orders import move_item
from db.items import all, delete_item, get as item_get, update as item_update
from db.main import engine
from db.models import Item


ITEM_COLUMNS = ['id', 'name', 'creator_id']
app = typer.Typer()


@app.command('get')
def get(
    id: Annotated[Optional[int], typer.Argument()] = None
):
    table = PrettyTable()
    table.field_names = ITEM_COLUMNS

    with Session(engine) as session:
        if id is None:
            recs = all(session)
        else:
            rec: Optional[Item] = item_get(session, id)
            if rec is None:
                typer.echo('Error: no such item.', err=True)
                raise typer.Exit(code=1)
            recs = [rec]

    data = [[item.model_dump()[key] for key in ITEM_COLUMNS] for item in recs]
    table.add_rows(data)
    print(table)


@app.command('remove')
def remove(
    id: Annotated[int, typer.Argument()]
):
    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            typer.echo('Error: no such item.', err=True)
            raise typer.Exit(code=1)

        delete_item(session, item)


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
        changes['due_on'] = datetime.fromisoformat(due_on)

    if not changes:
        typer.echo('Error: nothing to update — supply at least one option.', err=True)
        raise typer.Exit(code=1)

    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            typer.echo('Error: no such item.', err=True)
            raise typer.Exit(code=1)
        item_update(session, item, changes)
        typer.echo(f'Item {id} updated.')


@app.command('reorder')
def reorder(
    id: Annotated[int, typer.Argument(help="ID of the item to move")],
    after_id: Annotated[Optional[int], typer.Argument(help="ID of the item to move after, or omit to move to front")] = None,
):
    with Session(engine) as session:
        item: Optional[Item] = item_get(session, id)
        if item is None:
            typer.echo('Error: no such item.', err=True)
            raise typer.Exit(code=1)

        if after_id is not None:
            after_item: Optional[Item] = item_get(session, after_id)
            if after_item is None:
                typer.echo('Error: no such after_id item.', err=True)
                raise typer.Exit(code=1)
            if after_item.creator_id != item.creator_id:
                typer.echo('Error: items belong to different users.', err=True)
                raise typer.Exit(code=1)

        entry = move_item(session, item.creator_id, id, after_id)
        typer.echo(f'Item {id} moved, order_key={entry.order_key}')
