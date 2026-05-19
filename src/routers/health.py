from fastapi import APIRouter, Request

from app.config import get_settings
from app.rate_limit import limiter

_settings = get_settings()

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("")
@limiter.limit(_settings.RATE_LIMIT_HEALTH)
async def health_check(request: Request):
    return {"ok": 1}
