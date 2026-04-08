
import datetime as dt
import hashlib
import secrets
from typing import Optional

from sqlmodel import Session, select

from db.models import UserVerification


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_verification(
    session: Session,
    user_id: int,
    expire_minutes: int = 15,
) -> str:
    """Create a verification record and return the raw (unhashed) token."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=expire_minutes)
    record = UserVerification(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return raw_token


def consume_verification(
    session: Session,
    raw_token: str,
) -> Optional[UserVerification]:
    """Validate and consume a token. Returns the record if valid, else None.

    A token is valid if it exists, has not been used, and has not expired.
    On success the record is marked as used.
    """
    token_hash = _hash_token(raw_token)
    now = dt.datetime.now(dt.timezone.utc)
    record = session.exec(
        select(UserVerification)
        .where(UserVerification.token_hash == token_hash)
        .where(UserVerification.used == False)
        .where(UserVerification.expires_at > now)
    ).first()
    if record is None:
        return None
    record.used = True
    session.add(record)
    session.commit()
    return record
