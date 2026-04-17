import datetime

import jwt
import pytest
from fastapi import Request
from starlette.datastructures import Headers
from starlette.types import Scope

from app.config import Settings
from app.rate_limit import _get_rate_limit_key

_settings = Settings()


def _make_request(headers: dict, client_host: str = "127.0.0.1") -> Request:
    """Build a minimal Starlette Request with the given headers and client IP."""
    raw_headers = Headers(headers=headers).raw
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, _settings.SECRET_KEY, algorithm=_settings.ALGORITHM)


class TestGetRateLimitKey:
    def test_returns_username_from_valid_jwt(self):
        token = _make_token({"sub": "alice"})
        req = _make_request({"Authorization": f"Bearer {token}"})
        assert _get_rate_limit_key(req) == "user:alice"

    def test_falls_back_to_ip_when_no_auth_header(self):
        req = _make_request({}, client_host="10.0.0.5")
        assert _get_rate_limit_key(req) == "ip:10.0.0.5"

    def test_falls_back_to_ip_on_malformed_token(self):
        req = _make_request({"Authorization": "Bearer thisisnot.a.validtoken"}, client_host="10.0.0.1")
        result = _get_rate_limit_key(req)
        assert result.startswith("ip:")

    def test_extracts_username_from_expired_token(self):
        # verify_signature=False in the key function means we still bucket by
        # username even when the token is expired — auth enforcement happens
        # separately in get_current_user().
        past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
        token = _make_token({"sub": "bob", "exp": past})
        req = _make_request({"Authorization": f"Bearer {token}"})
        assert _get_rate_limit_key(req) == "user:bob"

    def test_uses_first_ip_from_x_forwarded_for(self):
        req = _make_request({"X-Forwarded-For": "203.0.113.1, 10.0.0.2"})
        assert _get_rate_limit_key(req) == "ip:203.0.113.1"

    def test_falls_back_to_ip_when_bearer_prefix_missing(self):
        token = _make_token({"sub": "carol"})
        req = _make_request({"Authorization": token}, client_host="192.168.1.1")
        # No "Bearer " prefix — falls back to IP
        result = _get_rate_limit_key(req)
        assert result.startswith("ip:")

    def test_falls_back_to_ip_when_sub_is_absent(self):
        # Token with no "sub" claim — falls back to IP
        token = _make_token({"user": "dave"})
        req = _make_request({"Authorization": f"Bearer {token}"}, client_host="1.2.3.4")
        assert _get_rate_limit_key(req) == "ip:1.2.3.4"
