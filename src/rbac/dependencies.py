from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from db.main import get_session
from db.models import User, UserRole
from rbac.enforcer import get_enforcer
from routers.users import get_current_user


def get_user_roles(session: Session, user_id: int) -> list[str]:
    rows = session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    return [r.role for r in rows] or ["user"]


def require_permission(resource: str, action: str) -> Callable:
    async def _check(
        user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> User:
        enforcer = get_enforcer()
        roles = get_user_roles(session, user.id)
        if not any(enforcer.enforce(role, resource, action) for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return _check
