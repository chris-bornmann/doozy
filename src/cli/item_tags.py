from typing import Annotated

import typer
from prettytable import PrettyTable
from sqlmodel import Session, select

from db.main import engine
from db.models import Item, ItemTag, Tag

app = typer.Typer()


@app.command('add')
def add(
    item_id: Annotated[int, typer.Argument(help="ID of the item")],
    tag_id:  Annotated[int, typer.Argument(help="ID of the tag")],
):
    """Assign a tag to an item."""
    with Session(engine) as session:
        if session.get(Item, item_id) is None:
            typer.echo(f"Error: no item with id {item_id}.", err=True)
            raise typer.Exit(code=1)
        if session.get(Tag, tag_id) is None:
            typer.echo(f"Error: no tag with id {tag_id}.", err=True)
            raise typer.Exit(code=1)
        existing = session.exec(
            select(ItemTag)
            .where(ItemTag.item_id == item_id)
            .where(ItemTag.tag_id == tag_id)
        ).first()
        if existing:
            typer.echo("Error: that tag is already assigned to that item.", err=True)
            raise typer.Exit(code=1)
        session.add(ItemTag(item_id=item_id, tag_id=tag_id))
        session.commit()
    typer.echo(f"Tag {tag_id} assigned to item {item_id}.")


@app.command('delete')
def delete(
    item_id: Annotated[int, typer.Argument(help="ID of the item")],
    tag_id:  Annotated[int, typer.Argument(help="ID of the tag")],
):
    """Remove the association between a tag and an item."""
    with Session(engine) as session:
        entry = session.exec(
            select(ItemTag)
            .where(ItemTag.item_id == item_id)
            .where(ItemTag.tag_id == tag_id)
        ).first()
        if entry is None:
            typer.echo("Error: no such assignment.", err=True)
            raise typer.Exit(code=1)
        session.delete(entry)
        session.commit()
    typer.echo(f"Tag {tag_id} removed from item {item_id}.")


@app.command('items')
def list_items(
    tag_id: Annotated[int, typer.Argument(help="ID of the tag")],
):
    """List all items assigned to a specific tag."""
    with Session(engine) as session:
        if session.get(Tag, tag_id) is None:
            typer.echo(f"Error: no tag with id {tag_id}.", err=True)
            raise typer.Exit(code=1)
        rows = session.exec(
            select(Item)
            .join(ItemTag, ItemTag.item_id == Item.id)
            .where(ItemTag.tag_id == tag_id)
            .order_by(Item.name)
        ).all()

    table = PrettyTable(['id', 'name', 'priority', 'state'])
    table.align['name'] = 'l'
    for item in rows:
        table.add_row([item.id, item.name, item.priority, item.state])
    print(table)


@app.command('tags')
def list_tags(
    item_id: Annotated[int, typer.Argument(help="ID of the item")],
):
    """List all tags assigned to a specific item."""
    with Session(engine) as session:
        if session.get(Item, item_id) is None:
            typer.echo(f"Error: no item with id {item_id}.", err=True)
            raise typer.Exit(code=1)
        rows = session.exec(
            select(Tag)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item_id)
            .order_by(Tag.name)
        ).all()

    table = PrettyTable(['id', 'name'])
    table.align['name'] = 'l'
    for tag in rows:
        table.add_row([tag.id, tag.name])
    print(table)
