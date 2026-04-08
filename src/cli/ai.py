
from typing import Annotated

import typer
from prettytable import PrettyTable

from app.config import Settings
from routers.ai import parse_item_request

app = typer.Typer()


@app.command('request')
def ai_request(
    request: Annotated[str, typer.Argument(help="Natural language request, e.g. 'Create a new item called Buy milk'")],
):
    """Parse a natural language item request using Claude and print the result."""
    settings = Settings()
    if not settings.ANTHROPIC_API_KEY:
        typer.echo("Error: ANTHROPIC_API_KEY is not configured.", err=True)
        raise typer.Exit(code=1)

    try:
        parsed = parse_item_request(request, settings.ANTHROPIC_API_KEY)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Operation : {parsed.operation}")
    if parsed.item_id is not None:
        typer.echo(f"Item ID   : {parsed.item_id}")

    if parsed.fields:
        table = PrettyTable(["Field", "Value"])
        table.align["Field"] = "l"
        table.align["Value"] = "l"
        for key, value in parsed.fields.model_dump().items():
            if value is not None:
                table.add_row([key, value])
        if table.rows:
            typer.echo(table)

    if parsed.error:
        typer.echo(f"Error     : {parsed.error}", err=True)
        raise typer.Exit(code=1)
