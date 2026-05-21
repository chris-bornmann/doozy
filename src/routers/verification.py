
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from app.rate_limit import limiter
from sqlmodel import Session

from app.config import get_settings
from db.main import get_session
import services.verification as verification_service


_settings = get_settings()

router = APIRouter(
    prefix="/verify",
    tags=["verification"],
)


@router.get("/")
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def verify_token(
    request: Request,
    token: str,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    verification_service.verify_token(session, token)
    return RedirectResponse(f"{_settings.GUI_URL}login")
