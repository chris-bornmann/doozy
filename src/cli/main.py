import typer

from cli import db, items, open_api, users

app = typer.Typer()

app.add_typer(db.app, name="db")
app.add_typer(items.app, name="items")
app.add_typer(open_api.cli_app, name="swagger")
app.add_typer(users.app, name="users")


if __name__ == "__main__":
    app()

