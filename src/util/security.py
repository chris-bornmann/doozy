
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional, Union

import jwt

from fastapi import Depends, HTTPException, status
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.security import oauth2_scheme
from db.main import get_session
from db.models import User
from db.users import get_by_username


logger = logging.getLogger(__name__)

_settings = get_settings()


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
    expire = datetime.now(timezone.utc) + timedelta(minutes=_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, _settings.SECRET_KEY, algorithm=_settings.ALGORITHM)
    return encoded_jwt


def decode_token(
    token: str
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
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


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
) -> User:
    data = decode_token(token)
    if data.get('error'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid authentication credentials: {data['error']}',
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = data.get('sub')
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials: missing sub",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_by_username(session, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


if __name__ == '__main__':
    hashed = get_password_hash('2222222222')
    print(hashed)
