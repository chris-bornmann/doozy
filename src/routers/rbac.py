from typing import Annotated

from fastapi import APIRouter, Depends, Request
from app.config import get_settings
from app.rate_limit import limiter

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import User, UserRole
from rbac.dependencies import require_permission
from schemas import UserRolesSummary
from util.security import get_current_user
import services.rbac as rbac_service


_settings = get_settings()

router = APIRouter(
    prefix="/rbac",
    tags=["rbac"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)


class UserRoleForm(BaseModel):
    user_id: int
    role: str = Field(max_length=32, min_length=1)


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def list_user_roles(
    request: Request,
    _: Annotated[User, Depends(require_permission("rbac", "read"))],
    session: Session = Depends(get_session),
) -> list[UserRolesSummary]:
    return rbac_service.list_all_roles(session)


@router.get("/me/permissions")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def get_my_permissions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> dict[str, list[str]]:
    return rbac_service.get_permissions_for_user(session, current_user)


@router.get("/{user_id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def get_user_roles_endpoint(
    request: Request,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> list[str]:
    return rbac_service.get_roles_for_subject(session, current_user, user_id)


@router.post("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def add_user_role(
    request: Request,
    _: Annotated[User, Depends(require_permission("rbac", "write"))],
    data: UserRoleForm,
    session: Session = Depends(get_session),
) -> UserRole:
    return rbac_service.add_role(session, data.user_id, data.role)


@router.delete("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_user_role(
    request: Request,
    _: Annotated[User, Depends(require_permission("rbac", "delete"))],
    data: UserRoleForm,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    rbac_service.remove_role(session, data.user_id, data.role)
    return {"ok": True}
