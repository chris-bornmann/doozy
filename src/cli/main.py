import typer

from cli import ai, db, item_tags, items, open_api, tags, users, verification

app = typer.Typer()

app.add_typer(ai.app, name="ai")
app.add_typer(db.app, name="db")
app.add_typer(item_tags.app, name="item-tags")
app.add_typer(items.app, name="items")
app.add_typer(open_api.cli_app, name="swagger")
app.add_typer(tags.app, name="tags")
app.add_typer(users.app, name="users")
app.add_typer(verification.app, name="verify")


if __name__ == "__main__":
    app()

