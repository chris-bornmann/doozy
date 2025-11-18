import typer

from cli import items, users

app = typer.Typer()

app.add_typer(items.app, name="items")
app.add_typer(users.app, name="users")


if __name__ == "__main__":
    app()

