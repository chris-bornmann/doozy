
from sqlmodel import Session

from constants import FriendshipStatus
from db import friendships as db
from db.models import Friendship, User
from db.users import get as get_user, get_by_username
from exceptions import DoozyBadRequestError, DoozyConflictError, DoozyForbiddenError, DoozyNotFoundError
from schemas import FriendshipRead


def enrich_friendship(session: Session, friendship: Friendship) -> FriendshipRead:
    """Build a FriendshipRead with resolved usernames."""
    requester = get_user(session, friendship.requester_id)
    addressee = get_user(session, friendship.addressee_id)
    return FriendshipRead(
        id=friendship.id,
        requester=requester.username,
        addressee=addressee.username,
        status=friendship.status,
        created_on=friendship.created_on,
        updated_on=friendship.updated_on,
    )


def get_friendship(session: Session, friendship_id: int) -> Friendship:
    """Fetch a friendship by ID. Raises 404 if not found."""
    f = db.get(session, friendship_id)
    if f is None:
        raise DoozyNotFoundError("Friendship not found")
    return f


def request_friendship(session: Session, user: User, target_username: str) -> FriendshipRead:
    """Send a friend request. Raises 400 for self-request, 404 for unknown user, 409 for duplicate."""
    if target_username == user.username:
        raise DoozyBadRequestError("Cannot send a friend request to yourself")
    target = get_by_username(session, target_username)
    if target is None:
        raise DoozyNotFoundError("User not found")
    try:
        friendship = db.request(session, user.id, target.id)
    except ValueError:
        raise DoozyConflictError("Friend request already exists")
    return enrich_friendship(session, friendship)


def list_friends_stmt(user_id: int):
    """Statement for paginating accepted friends."""
    return db.friends_stmt(user_id)


def list_pending_stmt(user_id: int):
    """Statement for paginating pending received friend requests."""
    return db.pending_received_stmt(user_id)


def list_sent_stmt(user_id: int):
    """Statement for paginating sent friend requests."""
    return db.sent_stmt(user_id)


def accept_friendship(session: Session, user: User, friendship_id: int) -> FriendshipRead:
    """Accept a pending friend request. Only the addressee can accept."""
    friendship = get_friendship(session, friendship_id)
    if friendship.addressee_id != user.id:
        raise DoozyForbiddenError("Only the recipient can accept a friend request")
    if friendship.status != FriendshipStatus.PENDING:
        raise DoozyConflictError("Friend request is not pending")
    friendship = db.accept(session, friendship)
    return enrich_friendship(session, friendship)


def decline_friendship(session: Session, user: User, friendship_id: int) -> FriendshipRead:
    """Decline a pending friend request. Only the addressee can decline."""
    friendship = get_friendship(session, friendship_id)
    if friendship.addressee_id != user.id:
        raise DoozyForbiddenError("Only the recipient can decline a friend request")
    if friendship.status != FriendshipStatus.PENDING:
        raise DoozyConflictError("Friend request is not pending")
    friendship = db.decline(session, friendship)
    return enrich_friendship(session, friendship)


def remove_friendship(session: Session, user: User, friendship_id: int) -> None:
    """Remove a friendship. Only parties to the friendship can remove it."""
    friendship = get_friendship(session, friendship_id)
    if user.id not in (friendship.requester_id, friendship.addressee_id):
        raise DoozyForbiddenError("Not a party to this friendship")
    can_remove = (
        friendship.status == FriendshipStatus.ACCEPTED
        or (friendship.status == FriendshipStatus.PENDING and friendship.requester_id == user.id)
    )
    if not can_remove:
        raise DoozyConflictError("Cannot remove this friendship")
    db.remove(session, friendship)
