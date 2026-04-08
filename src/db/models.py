
import datetime as dt
from datetime import datetime

from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Relationship

from constants import Priority, State, UserState


class PriorityType(sa.TypeDecorator):
    """Stores Priority as an integer; returns a Priority enum on load."""
    impl = sa.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return int(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Priority(value)


class StateType(sa.TypeDecorator):
    """Stores State as an integer; returns a State enum on load."""
    impl = sa.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return int(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return State(value)


class UserStateType(sa.TypeDecorator):
    """Stores UserState as an integer; returns a UserState enum on load."""
    impl = sa.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return int(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return UserState(value)


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

    items: list['Item'] = Relationship(back_populates='creator', cascade_delete=True)


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


class UserItemOrder(SQLModel, table=True):
    """Stores a per-user fractional-index ordering key for each item."""

    __tablename__ = 'user_item_orders'

    user_id: int = Field(foreign_key='users.id', primary_key=True)
    item_id: int = Field(foreign_key='items.id', primary_key=True)
    order_key: str = Field(index=True)


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
    creator: User = Relationship(back_populates='items')

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
