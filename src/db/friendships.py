
import datetime as dt
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Session, select

from constants import FriendshipStatus
from db.models import Friendship, User


def get(session: Session, friendship_id: int) -> Optional[Friendship]:
    return session.get(Friendship, friendship_id)


def get_between(session: Session, user_a: int, user_b: int) -> Optional[Friendship]:
    """Find any friendship row between two users, regardless of direction."""
    stmt = select(Friendship).where(
        sa.or_(
            sa.and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
            sa.and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
        )
    )
    return session.exec(stmt).first()


def friends_stmt(user_id: int):
    """Paginate-ready select(User) for all accepted friends of user_id."""
    friend_ids_subq = (
        select(
            sa.case(
                (Friendship.requester_id == user_id, Friendship.addressee_id),
                else_=Friendship.requester_id,
            ).label("friend_id")
        )
        .where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            sa.or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
        .subquery()
    )
    return select(User).where(User.id.in_(select(friend_ids_subq.c.friend_id)))


def pending_received_stmt(user_id: int):
    """Select PENDING requests addressed to user_id."""
    return select(Friendship).where(
        Friendship.addressee_id == user_id,
        Friendship.status == FriendshipStatus.PENDING,
    )


def sent_stmt(user_id: int):
    """Select all requests sent by user_id (any status)."""
    return select(Friendship).where(Friendship.requester_id == user_id)


def request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """
    Create a new friendship request, or re-activate a DECLINED one.
    Raises ValueError("friendship_exists") if a conflicting row already exists.
    """
    existing = get_between(session, requester_id, addressee_id)
    if existing:
        can_rerequest = (
            existing.status == FriendshipStatus.DECLINED
            and existing.requester_id == requester_id
        )
        if not can_rerequest:
            raise ValueError("friendship_exists")
        existing.status = FriendshipStatus.PENDING
        existing.updated_on = dt.datetime.now(dt.timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    friendship = Friendship(requester_id=requester_id, addressee_id=addressee_id)
    session.add(friendship)
    session.commit()
    session.refresh(friendship)
    return friendship


def _set_status(session: Session, friendship: Friendship, status: FriendshipStatus) -> Friendship:
    friendship.status = status
    friendship.updated_on = dt.datetime.now(dt.timezone.utc)
    session.add(friendship)
    session.commit()
    session.refresh(friendship)
    return friendship


def accept(session: Session, friendship: Friendship) -> Friendship:
    return _set_status(session, friendship, FriendshipStatus.ACCEPTED)


def decline(session: Session, friendship: Friendship) -> Friendship:
    return _set_status(session, friendship, FriendshipStatus.DECLINED)


def remove(session: Session, friendship: Friendship) -> None:
    session.delete(friendship)
    session.commit()
