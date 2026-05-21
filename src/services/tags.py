
from sqlmodel import Session, select

from db import tags as db_tags
from db.models import Tag, User
from exceptions import DoozyConflictError, DoozyForbiddenError, DoozyNotFoundError
from rbac.dependencies import get_user_roles


def list_tags_stmt(match: str | None = None):
    """Statement for paginating tags, optionally filtered by name substring."""
    stmt = select(Tag).order_by(Tag.name)
    if match is not None:
        stmt = stmt.where(Tag.name.contains(match))
    return stmt


def create_tag(session: Session, user: User, name: str) -> Tag:
    """Create a tag. Raises 409 if a tag with that name already exists."""
    if db_tags.get_by_name(session, name) is not None:
        raise DoozyConflictError("Tag already exists")
    return db_tags.create(session, name=name, creator_id=user.id)


def delete_tag(session: Session, user: User, tag_id: int) -> None:
    """
    Delete a tag.
    Admins may delete any tag (all item assignments are cascade-deleted).
    Regular users may only delete tags they created that have no item assignments.
    """
    tag = db_tags.get(session, tag_id)
    if tag is None:
        raise DoozyNotFoundError("Tag not found")

    roles = get_user_roles(session, user.id)
    is_admin = "admin" in roles

    if is_admin:
        db_tags.delete(session, tag)
    else:
        if tag.creator_id != user.id:
            raise DoozyForbiddenError("You can only delete tags you created")
        if db_tags.is_assigned(session, tag_id):
            raise DoozyForbiddenError("Tag is assigned to one or more work items")
        db_tags.delete(session, tag)
