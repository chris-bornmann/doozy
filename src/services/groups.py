
from sqlalchemy import exc
from sqlmodel import Session

from constants import FriendshipStatus
from db import friendships as db_friends
from db import groups as db
from db.models import Group, User
from db.users import get as get_user, get_by_username
from exceptions import DoozyConflictError, DoozyForbiddenError, DoozyNotFoundError
from schemas import GroupRead


def enrich_group(session: Session, group: Group) -> GroupRead:
    """Build a GroupRead with resolved owner username and member list."""
    owner = get_user(session, group.owner_id)
    group_members = db.members(session, group.id)
    return GroupRead(
        id=group.id,
        name=group.name,
        owner=owner.username,
        members=[u.username for u in group_members],
        created_on=group.created_on,
    )


def list_groups_stmt(user_id: int):
    """Statement for paginating groups the user belongs to."""
    return db.my_groups_stmt(user_id)


def create_group(session: Session, user: User, name: str) -> GroupRead:
    """Create a group owned by user. Raises 409 if a group with that name exists."""
    try:
        group = db.create(session, name=name, owner_id=user.id)
    except exc.IntegrityError:
        raise DoozyConflictError("A group with that name already exists")
    return enrich_group(session, group)


def get_group(session: Session, user: User, group_id: int) -> GroupRead:
    """Fetch a group. User must be a member."""
    group = db.get(session, group_id)
    if group is None:
        raise DoozyNotFoundError("Group not found")
    if db.get_member(session, group_id, user.id) is None:
        raise DoozyForbiddenError("Not a member of this group")
    return enrich_group(session, group)


def delete_group(session: Session, user: User, group_id: int) -> None:
    """Delete a group. Only the owner can delete."""
    group = db.get(session, group_id)
    if group is None:
        raise DoozyNotFoundError("Group not found")
    if group.owner_id != user.id:
        raise DoozyForbiddenError("Only the owner can delete a group")
    db.delete(session, group)


def add_member(session: Session, user: User, group_id: int, target_username: str) -> GroupRead:
    """Add a member to a group. Owner only; target must be an accepted friend."""
    group = db.get(session, group_id)
    if group is None:
        raise DoozyNotFoundError("Group not found")
    if group.owner_id != user.id:
        raise DoozyForbiddenError("Only the owner can add members")
    target = get_by_username(session, target_username)
    if target is None:
        raise DoozyNotFoundError("User not found")
    if db.get_member(session, group_id, target.id) is not None:
        raise DoozyConflictError("User is already a member of this group")
    friendship = db_friends.get_between(session, user.id, target.id)
    if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
        raise DoozyForbiddenError("You can only add friends to a group")
    db.add_member(session, group_id, target.id)
    return enrich_group(session, group)


def remove_member(session: Session, user: User, group_id: int, target_username: str) -> None:
    """Remove a member from a group. Owner only; cannot remove self."""
    group = db.get(session, group_id)
    if group is None:
        raise DoozyNotFoundError("Group not found")
    if group.owner_id != user.id:
        raise DoozyForbiddenError("Only the owner can remove members")
    target = get_by_username(session, target_username)
    if target is None:
        raise DoozyNotFoundError("User not found")
    if target.id == group.owner_id:
        raise DoozyConflictError("The owner cannot be removed from their own group")
    gm = db.get_member(session, group_id, target.id)
    if gm is None:
        raise DoozyNotFoundError("User is not a member of this group")
    db.remove_member(session, gm)
