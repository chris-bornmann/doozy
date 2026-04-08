import asyncio
from typing import Annotated

import typer
from sqlmodel import Session

from db.main import engine
from db.users import get_by_username
from db.verification import create_verification
from routers.verification import send_verification_email
from app.config import Settings

app = typer.Typer()


@app.command("send")
def send(
    username: Annotated[str, typer.Argument(help="Username (email) of the user to send a verification email to")],
):
    """Create a verification token and send a welcome email to the given user."""
    settings = Settings()

    with Session(engine) as session:
        user = get_by_username(session, username)
        if user is None:
            typer.echo(f"Error: no user found with username '{username}'", err=True)
            raise typer.Exit(code=1)

        raw_token = create_verification(session, user.id, settings.VERIFICATION_EXPIRE_MINUTES)

        try:
            asyncio.run(send_verification_email(user, raw_token))
        except Exception as exc:
            typer.echo(f"Failed to send email: {exc}", err=True)
            raise typer.Exit(code=1)
        else:
            typer.echo(f"Verification email sent to {username}.")