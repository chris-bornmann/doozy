
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import jwt

from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlmodel import Session

from app.config import Settings
from db.models import User
from db.users import get_by_username


logger = logging.getLogger(__name__)

settings = Settings()


class Token(BaseModel):
    # A struct that lets us pass the token back to the web client.  FastAPI
    # knows how to turn BaseModel into JSON.
    access_token: str
    token_type: str


password_hash = PasswordHash.recommended()


def verify_password(
    password: str,
    hashed: str
) -> bool:
    return password_hash.verify(password, hashed)


def get_password_hash(
    password: str
) -> str:
    return password_hash.hash(password)


def encode_token(
    data: dict[str, Union[datetime, str]],
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(
    token: str
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        logger.warning("Token expired")
        return {'error': 'Invalid credentials'}
    except InvalidTokenError:
        logger.warning("Invalid token")
        return {'error': 'Invalid credentials'}


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> Optional[User]:
    user = get_by_username(session, username)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None

    return user


if __name__ == '__main__':
    hashed = get_password_hash('2222222222')
    print(hashed)
