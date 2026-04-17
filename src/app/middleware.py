import logging
import time
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from fastapi import Request, Response


_SENSITIVE_PARAMS = {"token", "code", "password"}


def _redact_url(url) -> str:
    parsed = urlparse(str(url))
    if not parsed.query:
        return str(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    redacted = {k: ["***"] if k in _SENSITIVE_PARAMS else v for k, v in params.items()}
    return parsed._replace(query=urlencode(redacted, doseq=True)).geturl()


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        file_name: str
    ):
        logging.basicConfig(
            filename=file_name,
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="%Y%m%d",
        )
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response = await call_next(request)
        logging.info(f"{request.method} {_redact_url(request.url)} - {response.status_code}")
        
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        return response

