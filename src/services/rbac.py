
from collections import defaultdict

from fastapi import HTTPException, status
from sqlmodel import Session

from db import users as db_users
from db.models import User, UserRole
from rbac.dependencies import get_user_roles
from rbac.enforcer import get_enforcer
from rbac.roles import (
    assign_role,
    get_all_assignments,
    get_role_assignment,
    get_roles,
    revoke_role,
)
from schemas import UserRolesSummary


def list_all_roles(session: Session) -> list[UserRolesSummary]:
    """Aggregate all user roles with usernames."""
    role_rows = get_all_assignments(session)
    roles_by_user: dict[int, list[str]] = defaultdict(list)
    for row in role_rows:
        roles_by_user[row.user_id].append(row.role)
    users = db_users.all(session)
    return [
        UserRolesSummary(
            user_id=u.id,
            username=u.username,
            roles=roles_by_user.get(u.id, []),
        )
        for u in users
    ]


def get_permissions_for_user(session: Session, user: User) -> dict[str, list[str]]:
    """Return all resource → actions the user has permission to perform."""
    enforcer = get_enforcer()
    user_roles = get_user_roles(session, user.id)
    all_pairs = {(rule[1], rule[2]) for rule in enforcer.get_policy()}
    result: dict[str, list[str]] = {}
    for resource, action in sorted(all_pairs):
        if any(enforcer.enforce(role, resource, action) for role in user_roles):
            result.setdefault(resource, []).append(action)
    return result


def get_roles_for_subject(session: Session, requesting_user: User, subject_id: int) -> list[str]:
    """Return roles for subject_id. Self-lookup always allowed; others require rbac/read."""
    if requesting_user.id != subject_id:
        enforcer = get_enforcer()
        roles = get_user_roles(session, requesting_user.id)
        if not any(enforcer.enforce(role, "rbac", "read") for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
    if db_users.get(session, subject_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    return get_roles(session, subject_id)


def add_role(session: Session, user_id: int, role: str) -> UserRole:
    """Assign a role to a user. Raises 422 for invalid roles, 409 for duplicates."""
    valid_roles = {rule[0] for rule in get_enforcer().get_policy()}
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid role '{role}'. Valid roles: {sorted(valid_roles)}",
        )
    if db_users.get(session, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if get_role_assignment(session, user_id, role) is not None:
        raise HTTPException(status_code=409, detail="Role already assigned to user")
    return assign_role(session, user_id, role)


def remove_role(session: Session, user_id: int, role: str) -> None:
    """Revoke a role from a user. Raises 404 if the assignment doesn't exist."""
    if db_users.get(session, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if get_role_assignment(session, user_id, role) is None:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    revoke_role(session, user_id, role)
