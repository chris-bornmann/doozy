import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


def _get_rate_limit_key(request: Request) -> str:
    """
    Returns a stable key for rate-limit bucketing.

    For authenticated requests, extracts the username from the JWT 'sub' claim.
    We intentionally skip signature verification here — the actual cryptographic
    check still happens in get_current_user(). We only need a stable identity
    string for bucketing, so the extra verification would just be redundant work.

    Falls back to client IP for unauthenticated routes or malformed/missing tokens.
    """
    auth: str | None = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        raw_token = auth[len("Bearer "):]
        try:
            import jwt  # PyJWT — already a project dependency
            payload = jwt.decode(
                raw_token,
                options={"verify_signature": False},
                algorithms=["HS256"],
            )
            sub: str | None = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            logger.debug("Rate limit key: JWT decode failed, falling back to IP")

    # Use the first IP from X-Forwarded-For when running behind a reverse proxy.
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(key_func=_get_rate_limit_key)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return structured JSON on 429 instead of SlowAPI's plain-text default."""
    retry_after = request.headers.get("Retry-After", "60")
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}", "retry_after": retry_after},
        headers={"Retry-After": retry_after},
    )
