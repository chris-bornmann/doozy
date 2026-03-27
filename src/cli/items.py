from typing import Annotated, Optional

import typer
from prettytable import PrettyTable

from db.items import all, get as item_get, remove as item_remove
from db.models import Item


KEYS = ['id', 'name', 'creator_id']
app = typer.Typer()


@app.command('get')
def get(
    id: Annotated[Optional[int], typer.Argument()] = None
):
    table = PrettyTable()
    table.field_names = KEYS

    # import pdb; pdb.set_trace()
    if id is None:
        recs = all()
    else:
        rec: Optional[Item] = item_get(id)
        if rec is None:
            print('No such item')
            raise typer.Exit(code=1)
        recs = [rec]

    data = [[item.dict()[key] for key in KEYS] for item in recs]
    table.add_rows(data)
    print(table)


@app.command('remove')
def remove(
    id: Annotated[int, typer.Argument()]
):
    item: Optional[Item] = item_get(id)
    if item is None:
        print('No such item')
        raise typer.Exit(code=1)

    item_remove(item)
