
import logging
import ssl

import aiosmtplib
import certifi
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.rate_limit import limiter
from sqlmodel import Session

from app.config import Settings
from constants import UserState
from db.main import get_session
from db.models import User
from db.users import get as get_user
from db.verification import create_verification, consume_verification

logger = logging.getLogger(__name__)

settings = Settings()

router = APIRouter(
    prefix="/verify",
    tags=["verification"],
)


def _verification_link(raw_token: str) -> str:
    return f"{settings.VERIFICATION_URL}verify?token={raw_token}"


async def send_verification_email(user: User, raw_token: str) -> None:
    link = _verification_link(raw_token)
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        f"Welcome to Doozy!\n\n"
        f"Please click the link below to verify your account. "
        f"This link is only valid for {settings.VERIFICATION_EXPIRE_MINUTES} minutes.\n\n"
        f"{link}\n\n"
        f"If you did not create a Doozy account, you can safely ignore this email.\n\n"
        f"— The Doozy Team"
    )
    msg = MIMEText(body)
    msg["Subject"] = "Welcome to Doozy — verify your account"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = user.username  # username doubles as the email address

    tls_context = ssl.create_default_context(cafile=certifi.where())
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
            tls_context=tls_context,
            validate_certs=settings.SMTP_VALIDATE_CERTS,
        )
    except Exception as ex:
        logger.exception("Failed to send verification email to %s", user.username)
        raise


@router.get("/")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def verify_token(
    request: Request,
    token: str,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    record = consume_verification(session, token)
    if record is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user = get_user(session, record.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.state = UserState.AUTHENTICATED
    session.add(user)
    session.commit()

    return RedirectResponse(f"{settings.GUI_URL}login")
