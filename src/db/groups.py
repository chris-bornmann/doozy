
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Session, select

from db.models import Group, GroupMember, User


def get(session: Session, group_id: int) -> Optional[Group]:
    return session.get(Group, group_id)


def get_member(session: Session, group_id: int, user_id: int) -> Optional[GroupMember]:
    return session.get(GroupMember, (group_id, user_id))


def my_groups_stmt(user_id: int):
    """Paginate-ready select(Group) for all groups user_id belongs to."""
    return (
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user_id)
    )


def members(session: Session, group_id: int) -> list[User]:
    """Return all User rows that are members of group_id."""
    stmt = (
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    return list(session.exec(stmt).all())


def create(session: Session, name: str, owner_id: int) -> Group:
    """Create a group and add the owner as its first member."""
    group = Group(name=name, owner_id=owner_id)
    session.add(group)
    session.flush()  # populate group.id before inserting member row
    session.add(GroupMember(group_id=group.id, user_id=owner_id))
    session.commit()
    session.refresh(group)
    return group


def add_member(session: Session, group_id: int, user_id: int) -> GroupMember:
    gm = GroupMember(group_id=group_id, user_id=user_id)
    session.add(gm)
    session.commit()
    return gm


def remove_member(session: Session, gm: GroupMember) -> None:
    session.delete(gm)
    session.commit()


def delete(session: Session, group: Group) -> None:
    # Remove all members first (no cascade configured on this FK).
    session.exec(
        sa.delete(GroupMember).where(GroupMember.group_id == group.id)
    )
    session.delete(group)
    session.commit()
