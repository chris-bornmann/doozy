
import datetime as dt
from datetime import datetime

from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Relationship

from constants import Priority, State, UserState


def _make_enum_type(enum_class):
    """Return a TypeDecorator class that persists *enum_class* as an integer."""
    class _EnumType(sa.TypeDecorator):
        impl = sa.Integer
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return int(value) if value is not None else None

        def process_result_value(self, value, dialect):
            return enum_class(value) if value is not None else None

    return _EnumType


PriorityType  = _make_enum_type(Priority)
StateType     = _make_enum_type(State)
UserStateType = _make_enum_type(UserState)


class UserNoSecret(SQLModel):

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=32, min_length=8)
    enabled: bool = True
    full_name: Optional[str] = Field(default=None, max_length=128)
    state: UserState = Field(
        default=UserState.NEW,
        sa_column=sa.Column(UserStateType(), nullable=False),
    )

    created_on: datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True))
    )


class User(UserNoSecret, table=True):

    __tablename__ = 'users'

    password: str = Field(max_length=128, min_length=10)

    items: list['Item'] = Relationship(
        back_populates='creator',
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "[Item.creator_id]"},
    )


class UserVerification(SQLModel, table=True):
    """One-time verification token sent to a new user via email."""

    __tablename__ = 'user_verifications'

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)

    # SHA-256 hash of the raw token (only the raw token is sent in the email)
    token_hash: str = Field(index=True)

    expires_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)


class Tag(SQLModel, table=True):

    __tablename__ = 'tags'

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=16, unique=True, index=True)


class ItemTag(SQLModel, table=True):
    """Junction table linking items to tags."""

    __tablename__ = 'item_tags'

    item_id: int = Field(foreign_key='items.id', primary_key=True)
    tag_id: int = Field(foreign_key='tags.id', primary_key=True)


class UserItemOrder(SQLModel, table=True):
    """Stores a per-user fractional-index ordering key for each item."""

    __tablename__ = 'user_item_orders'

    user_id: int = Field(foreign_key='users.id', primary_key=True)
    item_id: int = Field(foreign_key='items.id', primary_key=True)
    order_key: str = Field(index=True)


class UserRole(SQLModel, table=True):
    """Maps a user to a named role for RBAC enforcement."""

    __tablename__ = 'user_roles'
    __table_args__ = (sa.UniqueConstraint('user_id', 'role'),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    role: str = Field(max_length=32, index=True)


class Item(SQLModel, table=True):

    __tablename__ = 'items'

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str = Field(max_length=32, min_length=8)
    description: Optional[str] = Field(default=None, max_length=128)

    priority: Optional[Priority] = Field(
        default=None,
        sa_column=sa.Column(PriorityType(), nullable=True),
    )

    state: State = Field(
        default=State.NEW,
        sa_column=sa.Column(StateType(), nullable=False),
    )

    creator_id: int = Field(foreign_key=User.__tablename__ + '.id')
    creator: User = Relationship(
        back_populates='items',
        sa_relationship_kwargs={"foreign_keys": "[Item.creator_id]"},
    )

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
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    completed_by_id: Optional[int] = Field(
        default=None,
        foreign_key=User.__tablename__ + '.id',
        nullable=True,
    )
    updated_on: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"onupdate": lambda: dt.datetime.now(dt.timezone.utc)}
    )
