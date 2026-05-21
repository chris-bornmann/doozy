from enum import Enum
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Query, Request, Response
from app.config import get_settings
from app.rate_limit import limiter

from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from sqlmodel import Session

from app.security import oauth2_scheme
from db.main import get_session
from db.models import User
from rbac.dependencies import require_permission
from schemas import Item as FormItem, ItemFilter, ItemRead, PatchItem, Reorder
import services.items as item_service


class SortBy(str, Enum):
    priority   = "priority"
    created_on = "created_on"
    due_on     = "due_on"
    state      = "state"
    custom     = "custom"


_settings = get_settings()

router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(oauth2_scheme)],
)

T = TypeVar("T")

CustomPage = CustomizedPage[
    Page[T],
    UseParamsFields(size=Query(2, ge=1, le=1000)),
]


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_items(
    request: Request,
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
) -> CustomPage[ItemRead]:
    """
    Fetch work items visible to the current user.

    This method doesn't have much use today because we're typically interested in
    "visible to" rather than "created by", but it's here for completeness and
    future use.  The /search endpoint is more likely to be used, and it supports
    the same sorting options plus filtering.
    """
    stmt = item_service.get_sorted_items_stmt(user.id, sort_by, reverse)
    return paginate(session, stmt, transformer=lambda items: item_service.enrich_items(session, items))


@router.post('/search')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def search_items(
    request: Request,
    *,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    session: Session = Depends(get_session),
    sort_by: SortBy = Query(default=SortBy.created_on),
    reverse: bool = Query(default=False),
    filter: ItemFilter,
) -> CustomPage[ItemRead]:
    stmt = item_service.get_sorted_items_stmt(user.id, sort_by, reverse)
    stmt = item_service.apply_filters(stmt, filter)
    return paginate(session, stmt, transformer=lambda items: item_service.enrich_items(session, items))


@router.get("/{id}")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def read_item(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "read"))],
    id: int,
    session: Session = Depends(get_session),
) -> ItemRead:
    item, _ = item_service.get_item(session, user, id)
    return item_service.enrich_items(session, [item])[0]


@router.post('/')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def post_item(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    data: Annotated[FormItem, Depends()],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    item_id = item_service.create_item(session, user, data)
    return {'id': item_id}


@router.patch('/{id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def patch_item(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    data: PatchItem,
    session: Session = Depends(get_session),
) -> ItemRead:
    return item_service.update_item(session, user, id, data.model_dump(include=data.model_fields_set))


@router.post('/{id}/reorder')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def reorder_item(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    data: Reorder,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    entry = item_service.reorder_item(session, user, id, data.after_id)
    return {'order_key': entry.order_key}


@router.post('/{id}/assign/user/{username}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def assign_to_user(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    username: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Change the owner of an item.  The "owner" is just the DRI."""
    item_service.assign_to_user(session, user, id, username)
    return {"ok": True}


@router.post('/{id}/assign/group/{group_id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def assign_to_group(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    group_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item_service.assign_to_group(session, user, id, group_id)
    return {"ok": True}


@router.delete('/{id}/assign/group')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def unassign_group(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "write"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item_service.unassign_group(session, user, id)
    return {"ok": True}


@router.delete('/{id}')
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def remove_item(
    request: Request,
    user: Annotated[User, Depends(require_permission("items", "delete"))],
    id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    item_service.delete_item(session, user, id)
    return {'ok': True}


@router.options('/search')
async def options_items_search() -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.options('/{id}/assign/user/{username}')
async def options_assign_user(id: int, username: str) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.options('/{id}/assign/group/{group_id}')
async def options_assign_group(id: int, group_id: int) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)


@router.options('/{id}/assign/group')
async def options_unassign_group(id: int) -> Response:
    return Response(headers={"Allow": "DELETE, OPTIONS"}, status_code=204)


@router.options('/')
async def options_items() -> Response:
    return Response(headers={"Allow": "GET, POST, OPTIONS"}, status_code=204)


@router.options('/{id}')
async def options_item(id: int) -> Response:
    return Response(headers={"Allow": "GET, PATCH, DELETE, OPTIONS"}, status_code=204)


@router.options('/{id}/reorder')
async def options_item_reorder(id: int) -> Response:
    return Response(headers={"Allow": "POST, OPTIONS"}, status_code=204)
