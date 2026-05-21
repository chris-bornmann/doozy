
class DoozyError(Exception):
    """Base class for all application domain errors."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class DoozyNotFoundError(DoozyError):
    """Raised when a requested resource does not exist."""
    pass


class DoozyForbiddenError(DoozyError):
    """Raised when the current user lacks permission to perform an action."""
    pass


class DoozyConflictError(DoozyError):
    """Raised when an action conflicts with existing state (e.g. duplicate record)."""
    pass


class DoozyBadRequestError(DoozyError):
    """Raised when the request itself is invalid (e.g. self-referential operation)."""
    pass
