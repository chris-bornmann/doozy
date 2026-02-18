from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from pwdlib import PasswordHash
from pydantic import BaseModel

from db.models import User
from db.users import get_by_username


# Generated with "openssl rand -hex 32".  This should be stored securely,
# not in the source!
SECRET_KEY = '2d68d76f35fa6221418afa625442252398639a94b037eade4cf2b19ce7894ad5'

ALGORITHM = "HS256"

# This should be configurable.
ACCESS_TOKEN_EXPIRE_MINUTES = 60


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
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(
    token: str
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        print("Token expired")
        return {'error': 'Token expired'}
    except InvalidTokenError:
        print("Invalid token")
        return {'error': 'Invalid token'}


def authenticate_user(
    username: str,
    password: str
) -> Optional[User]:
    user = get_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None

    return user


if __name__ == '__main__':
    hashed = get_password_hash('2222222222')
    print(hashed)
