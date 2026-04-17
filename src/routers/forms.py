
import datetime as dt
from datetime import date, datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from constants import Priority, State, FriendshipStatus


class Item(BaseModel):
    name: str = Field(max_length=32, min_length=8)
    description: Optional[str] = Field(default=None, max_length=128)
    priority: Optional[Priority] = Field(default=None)
    due_on: Optional[datetime] = Field(default=None)


class PatchItem(BaseModel):
    name: Optional[str] = Field(default=None, max_length=32, min_length=8)
    description: Optional[str] = Field(default=None, max_length=128)
    due_on: Optional[datetime] = Field(default=None)
    priority: Optional[Priority] = Field(default=None)
    state: Optional[State] = Field(default=None)


class Reorder(BaseModel):
    after_id: Optional[int] = None


class ItemFilter(BaseModel):
    name: Optional[str] = None
    state: list[State] = []
    priority: list[Priority] = []

    @field_validator('state', mode='before')
    @classmethod
    def parse_state(cls, v: list[Any]) -> list[State]:
        return [State[s.upper()] if isinstance(s, str) else s for s in v]

    @field_validator('priority', mode='before')
    @classmethod
    def parse_priority(cls, v: list[Any]) -> list[Priority]:
        return [Priority[p.upper()] if isinstance(p, str) else p for p in v]
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    created_on: Optional[date] = None
    due_after: Optional[datetime] = None
    due_before: Optional[datetime] = None
    due_on: Optional[date] = None
    completed_after: Optional[datetime] = None
    completed_before: Optional[datetime] = None
    completed_on: Optional[date] = None
    tags: list[str] = []
    group_ids: list[int] = []


class ItemRead(BaseModel):
    """Item response model — includes all Item fields plus current ownership info."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    name: str
    description: Optional[str]
    priority: Optional[Priority]
    state: State
    creator_id: int
    created_on: datetime
    due_on: Optional[datetime]
    completed_on: Optional[datetime]
    completed_by_id: Optional[int]
    updated_on: Optional[datetime]
    # Ownership fields — populated from ItemOwnership at response time
    owner: str           # username of the current owner
    group_id: Optional[int]  # group the item is shared with, if any


class FriendshipRead(BaseModel):
    id: int
    requester: str  # username of the requester
    addressee: str  # username of the addressee
    status: FriendshipStatus
    created_on: datetime
    updated_on: Optional[datetime] = None


class GroupRead(BaseModel):
    id: int
    name: str
    owner: str          # username of the owner
    members: list[str]  # usernames of all members (including owner)
    created_on: datetime


class User(BaseModel):
    
    # Should be using the same constraints as the DB model.
    username: str = Field(max_length=32, min_length=8)
    password: str = Field(max_length=32, min_length=10)
    enabled: bool = True
    full_name: Optional[str] = Field(max_length=128)

