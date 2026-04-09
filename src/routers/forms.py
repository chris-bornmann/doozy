
import datetime as dt
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field

from constants import Priority, State


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


class User(BaseModel):
    
    # Should be using the same constraints as the DB model.
    username: str = Field(max_length=32, min_length=8)
    password: str = Field(max_length=32, min_length=10)
    enabled: bool = True
    full_name: Optional[str] = Field(max_length=128)

