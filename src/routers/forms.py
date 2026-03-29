
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field

from constants import Priority


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


class Reorder(BaseModel):
    after_id: Optional[int] = None


class User(BaseModel):
    
    # Should be using the same constraints as the DB model.
    username: str = Field(max_length=32, min_length=8)
    password: str = Field(max_length=32, min_length=10)
    enabled: bool = True
    full_name: Optional[str] = Field(max_length=128)

