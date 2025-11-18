from typing import Annotated, Optional

import typer
from prettytable import PrettyTable

from db.users import all, get as user_get, remove as user_remove
from db.models import User


KEYS = ['id', 'username', 'full_name']
app = typer.Typer()


@app.command('get')
def get(
    id: Annotated[Optional[int], typer.Argument()] = None
):
    table = PrettyTable()
    table.field_names = KEYS

    if id is None:
        recs = all()
    else:
        rec = user_get(id)
        if rec is None:
            print('No such user')
            raise typer.Exit(code=1)
        recs = [rec]

    data = [[user.dict()[key] for key in KEYS] for user in recs]
    table.add_rows(data)
    print(table)


@app.command('remove')
def remove(
    id: Annotated[int, typer.Argument()]
):
    user: Optional[User] = user_get(id)
    if user is None:
        print('No such user')
        raise typer.Exit(code=1)

    user_remove(user)
