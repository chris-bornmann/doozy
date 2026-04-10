from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.security import oauth2_scheme
from db.main import get_session
from db.models import User, UserRole
from db.users import get as get_user
from rbac.dependencies import get_user_roles, require_permission
from rbac.enforcer import get_enforcer
from rbac.roles import assign_role, get_roles, revoke_role
from routers.users import get_current_user


router = APIRouter(
    prefix="/rbac",
    tags=["rbac"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)


class UserRolesSummary(BaseModel):
    user_id: int
    username: str
    roles: list[str]


class UserRoleForm(BaseModel):
    user_id: int
    role: str = Field(max_length=32, min_length=1)


@router.get("/")
async def list_user_roles(
    _: Annotated[User, Depends(require_permission("rbac", "read"))],
    session: Session = Depends(get_session),
) -> list[UserRolesSummary]:
    role_rows = session.exec(select(UserRole)).all()
    roles_by_user: dict[int, list[str]] = defaultdict(list)
    for row in role_rows:
        roles_by_user[row.user_id].append(row.role)

    users = session.exec(select(User)).all()
    return [
        UserRolesSummary(
            user_id=u.id,
            username=u.username,
            roles=roles_by_user.get(u.id, []),
        )
        for u in users
    ]


@router.get("/me/permissions")
async def get_my_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> dict[str, list[str]]:
    enforcer = get_enforcer()
    user_roles = get_user_roles(session, current_user.id)

    # Derive all known (resource, action) pairs from the policy itself
    all_pairs = {(rule[1], rule[2]) for rule in enforcer.get_policy()}

    result: dict[str, list[str]] = {}
    for resource, action in sorted(all_pairs):
        if any(enforcer.enforce(role, resource, action) for role in user_roles):
            result.setdefault(resource, []).append(action)

    return result


@router.get("/{user_id}")
async def get_user_roles_endpoint(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> list[str]:
    if current_user.id != user_id:
        enforcer = get_enforcer()
        roles = get_user_roles(session, current_user.id)
        if not any(enforcer.enforce(role, "rbac", "read") for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    target = get_user(session, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    return get_roles(session, user_id)


@router.post("/")
async def add_user_role(
    _: Annotated[User, Depends(require_permission("rbac", "write"))],
    data: UserRoleForm,
    session: Session = Depends(get_session),
) -> UserRole:
    valid_roles = {rule[0] for rule in get_enforcer().get_policy()}
    if data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid role '{data.role}'. Valid roles: {sorted(valid_roles)}",
        )

    if get_user(session, data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = session.exec(
        select(UserRole)
        .where(UserRole.user_id == data.user_id)
        .where(UserRole.role == data.role)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role already assigned to user")

    return assign_role(session, data.user_id, data.role)


@router.delete("/")
async def remove_user_role(
    _: Annotated[User, Depends(require_permission("rbac", "delete"))],
    data: UserRoleForm,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    if get_user(session, data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = session.exec(
        select(UserRole)
        .where(UserRole.user_id == data.user_id)
        .where(UserRole.role == data.role)
    ).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Role assignment not found")

    revoke_role(session, data.user_id, data.role)
    return {"ok": True}
