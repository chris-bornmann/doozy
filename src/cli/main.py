import typer

from cli import db, items, users

app = typer.Typer()

app.add_typer(db.app, name="db")
app.add_typer(items.app, name="items")
app.add_typer(users.app, name="users")


if __name__ == "__main__":
    app()

