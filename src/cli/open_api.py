import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from app.main import app as fastapi_app


cli_app = typer.Typer()


@cli_app.command('create')
def create(
    out: Annotated[Path, typer.Argument(help="Output file path. Use a .json or .yaml/.yml extension.")] = Path("openapi.yaml"),
):
    """Generate the OpenAPI spec for the Doozy API."""
    schema = fastapi_app.openapi()

    with open(out, "w") as f:
        if out.suffix == ".json":
            json.dump(schema, f, indent=2)
        else:
            yaml.dump(schema, f, sort_keys=False)

    print(f"Spec written to {out}")
