from typing import Annotated, Optional

import typer
from prettytable import PrettyTable

from sqlmodel import Session

from db.main import engine
from db.users import all, get as user_get, remove as user_remove
from db.models import User


USER_COLUMNS = ['id', 'username', 'full_name', 'state']
app = typer.Typer()


@app.command('get')
def get(
    id: Annotated[Optional[int], typer.Argument()] = None
):
    table = PrettyTable()
    table.field_names = USER_COLUMNS

    with Session(engine) as session:
        if id is None:
            recs = all(session)
        else:
            rec = user_get(session, id)
            if rec is None:
                typer.echo('Error: no such user.', err=True)
                raise typer.Exit(code=1)
            recs = [rec]

    data = [[user.model_dump()[key] for key in USER_COLUMNS] for user in recs]
    table.add_rows(data)
    print(table)


@app.command('remove')
def remove(
    id: Annotated[int, typer.Argument()]
):
    with Session(engine) as session:
        user: Optional[User] = user_get(session, id)
        if user is None:
            typer.echo('Error: no such user.', err=True)
            raise typer.Exit(code=1)

        user_remove(session, user)
