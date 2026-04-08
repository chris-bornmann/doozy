from typing import Annotated, Optional

import typer
from prettytable import PrettyTable
from sqlalchemy import delete as sql_delete
from sqlmodel import Session, select

from db.main import engine
from db.models import ItemTag, Tag

app = typer.Typer()


@app.command('get')
def get(
    match: Annotated[Optional[str], typer.Option('--match', help="Substring to filter tags by")] = None,
):
    """List all tags in alphabetical order."""
    with Session(engine) as session:
        stmt = select(Tag).order_by(Tag.name)
        if match is not None:
            stmt = stmt.where(Tag.name.contains(match))
        rows = session.exec(stmt).all()

    table = PrettyTable(['id', 'name'])
    table.align['name'] = 'l'
    for tag in rows:
        table.add_row([tag.id, tag.name])
    print(table)


@app.command('add')
def add(
    name: Annotated[str, typer.Argument(help="Tag name (max 16 characters)")],
):
    """Add a new tag."""
    with Session(engine) as session:
        if session.exec(select(Tag).where(Tag.name == name)).first():
            typer.echo(f"Error: tag '{name}' already exists.", err=True)
            raise typer.Exit(code=1)
        tag = Tag(name=name)
        session.add(tag)
        session.commit()
        session.refresh(tag)
    typer.echo(f"Tag '{tag.name}' added with id {tag.id}.")


@app.command('delete')
def delete(
    id: Annotated[int, typer.Argument(help="ID of the tag to delete")],
):
    """Delete a tag and remove it from all items."""
    with Session(engine) as session:
        tag = session.get(Tag, id)
        if tag is None:
            typer.echo(f"Error: no tag with id {id}.", err=True)
            raise typer.Exit(code=1)
        name = tag.name
        session.exec(sql_delete(ItemTag).where(ItemTag.tag_id == id))
        session.delete(tag)
        session.commit()
    typer.echo(f"Tag '{name}' deleted.")
