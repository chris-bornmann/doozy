
from enum import Enum


class Priority(int, Enum):
    HIGH = 0
    MEDIUM = 1
    LOW = 2


class State(int, Enum):
    NEW = 0
    IN_PROGRESS = 1
    DONE = 2
    CANCELLED = 3
