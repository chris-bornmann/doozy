
import logging
import ssl

import aiosmtplib
import certifi
from email.mime.text import MIMEText
from sqlmodel import Session

from app.config import get_settings
from constants import UserState
from db import users as db_users
from db.models import User
from db.verification import consume_verification
from exceptions import DoozyBadRequestError, DoozyNotFoundError


logger = logging.getLogger(__name__)
_settings = get_settings()


def _verification_link(raw_token: str) -> str:
    return f"{_settings.VERIFICATION_URL}verify?token={raw_token}"


async def send_verification_email(user: User, raw_token: str) -> None:
    link = _verification_link(raw_token)
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        f"Welcome to Doozy!\n\n"
        f"Please click the link below to verify your account. "
        f"This link is only valid for {_settings.VERIFICATION_EXPIRE_MINUTES} minutes.\n\n"
        f"{link}\n\n"
        f"If you did not create a Doozy account, you can safely ignore this email.\n\n"
        f"— The Doozy Team"
    )
    msg = MIMEText(body)
    msg["Subject"] = "Welcome to Doozy — verify your account"
    msg["From"] = _settings.SMTP_FROM
    msg["To"] = user.username  # username doubles as the email address

    tls_context = ssl.create_default_context(cafile=certifi.where())
    try:
        await aiosmtplib.send(
            msg,
            hostname=_settings.SMTP_HOST,
            port=_settings.SMTP_PORT,
            username=_settings.SMTP_USERNAME,
            password=_settings.SMTP_PASSWORD,
            start_tls=True,
            tls_context=tls_context,
            validate_certs=_settings.SMTP_VALIDATE_CERTS,
        )
    except Exception:
        logger.exception("Failed to send verification email to %s", user.username)
        raise


def verify_token(session: Session, raw_token: str) -> User:
    """Consume a verification token and transition the user to AUTHENTICATED."""
    record = consume_verification(session, raw_token)
    if record is None:
        raise DoozyBadRequestError("Invalid or expired verification token")
    user = db_users.get(session, record.user_id)
    if user is None:
        raise DoozyNotFoundError("User not found")
    db_users.update_state(session, user, UserState.AUTHENTICATED)
    return user
