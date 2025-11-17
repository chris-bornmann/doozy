
import datetime as dt
from datetime import datetime

from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Priority(int, Enum):
    HIGH = 0
    MEDIUM = 1
    LOW = 2


class UserNoSecret(SQLModel):

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=32, min_length=8)
    enabled: bool = True
    full_name: Optional[str] = Field(default=None, max_length=128)

    created_on: datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True))
    )


class User(UserNoSecret, table=True):

    __tablename__ = 'users'

    password: str = Field(max_length=32, min_length=10)


class Item(SQLModel, table=True):

    __tablename__ = 'items'

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str = Field(max_length=32, min_length=8)
    description: Optional[str] = Field(default=None, max_length=128)

    priority: Optional[Priority] = Field(default=None)

    created_on: datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True))
    )
    due_on: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True))
    )
    completed_on: Optional[datetime] = Field(
        default=None,
        # sa_column=sa.Column(sa.DateTime(timezone=True))
    )
    updated_on: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"onupdate": lambda: dt.datetime.now(dt.timezone.utc)}
    )
