from fastapi import APIRouter, Request

from app.config import Settings
from app.rate_limit import limiter

_settings = Settings()

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("")
@limiter.limit(_settings.RATE_LIMIT_HEALTH)
async def health_check(request: Request):
    return {"ok": 1}
