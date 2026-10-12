from contextlib import asynccontextmanager
from typing import Annotated, Any, Optional

import aiosmtplib
import logfire
import uvicorn

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from db.main import db_create, get_session
from app.middleware import LoggingMiddleware, TimingMiddleware
from app.rate_limit import limiter, rate_limit_exceeded_handler
from exceptions import DoozyBadRequestError, DoozyConflictError, DoozyForbiddenError, DoozyNotFoundError
from routers import ai, friendships, groups, health, item_tags, items, rbac, tags, users, verification
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from util.security import authenticate_user, encode_token, Token

# configuration and oauth-related helpers
from app.config import get_settings

# helper imports for user creation in google flow
import secrets
from db.users import get_by_username, create_user
from util.security import get_password_hash
from sqlmodel import Session
import httpx
import re
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode


# load settings (reads environment or .env file)
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logfire.configure(token=_settings.LOGFIRE_TOKEN or None)
    logfire.instrument_fastapi(app)
    logfire.instrument_httpx()
    db_create()
    yield
    # Shutdown code


tags_metadata: list[dict[str, Any]] = [
    {
        "name": "items",
        "description": "Operations on work items.",
    },
    {
        "name": "users",
        "description": "User management.",
        "externalDocs": {
            "description": "External Admin Documentation",
            "url": "https://doozy.com/admin/docs",
        },
    },
]


# make sure the two required variables are present; we will use them a
# couple of times later when constructing URLs/requests.
if not _settings.GOOGLE_CLIENT_ID or not _settings.GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in the"
        " environment to use Google authentication"
    )

# OAuth endpoints used by the Google OpenID Connect flow
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# OAuth "state" protects Google sign-in against login CSRF: an attacker tricking
# a victim's browser into finishing a login as the *attacker*, so anything the
# victim then creates lands in the attacker's account.
#
# The GUI generates a random state, remembers it in the browser, and passes it
# to /login/google. We hand it to Google, Google returns it to /auth/google,
# and we include it in the redirect back to the GUI, which only accepts the
# token if the state matches the one it remembered. A login the victim did not
# start therefore has no matching state and is rejected.
#
# The value is echoed into the redirect URL, so only accept the short URL-safe
# strings the GUI generates.
_OAUTH_STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _require_oauth_state(
    state: Optional[str],
) -> str:
    """Return ``state`` if it is a well-formed OAuth state value, else raise 400."""
    if state is None or not _OAUTH_STATE_PATTERN.fullmatch(state):
        raise HTTPException(status_code=400, detail="Missing or invalid state parameter")
    return state

app = FastAPI(
    title="Doozy",
    description="The Doozy API",
    version="0.0.1",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(DoozyNotFoundError)
async def _handle_not_found(request: Request, exc: DoozyNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


@app.exception_handler(DoozyForbiddenError)
async def _handle_forbidden(request: Request, exc: DoozyForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.detail})


@app.exception_handler(DoozyConflictError)
async def _handle_conflict(request: Request, exc: DoozyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.detail})


@app.exception_handler(DoozyBadRequestError)
async def _handle_bad_request(request: Request, exc: DoozyBadRequestError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.detail})


@app.exception_handler(aiosmtplib.SMTPException)
async def _smtp_exception_handler(request: Request, exc: aiosmtplib.SMTPException) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        # They can't actually try again later, because the user was created...
        content={"detail": "Failed to send verification email. Please try again later."},
    )


app.add_middleware(LoggingMiddleware, file_name="/tmp/doozy.log")
app.add_middleware(TimingMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(friendships.router)
app.include_router(groups.router)
app.include_router(item_tags.router)
app.include_router(items.router)
app.include_router(rbac.router)
app.include_router(tags.router)
app.include_router(users.public_router)
app.include_router(users.router)
app.include_router(verification.router)

# Define allowed origins.  Eventually this should include an actual
# web hosted site where the GUI is served from.
origins = [
    "http://localhost:5173",  # Local dev/test.
    "http://localhost:8080",  # Local docker (exposed nginx port is 8080).
    "http://100.104.51.111:5173",  # Tailscale.
]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

# Permanent URLs too...
app.include_router(items.router, prefix="/v1/items", tags=["items", "v1"])
app.include_router(users.public_router, prefix="/v1/users", tags=["users", "v1"])
app.include_router(users.router, prefix="/v1/users", tags=["users", "v1"])

# Must be called after all routers are included so pagination deps are applied.
add_pagination(app)

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the main API!"}


# existing username/password login
@app.post(
    "/token",
    response_model=Token,
    responses={
        401: {
            "description": "Authentication failed",
            "content": {"application/json": {"example": {"detail": "Incorrect username or password"}}},
        },
    },
)
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> Token:
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        # omit WWW-Authenticate header so browsers/clients can read JSON body
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = encode_token(data={"sub": user.username})
    return Token(access_token=access_token, token_type="bearer")


# oauth2 endpoints for Google
@app.get("/login/google")
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def login_google(request: Request):
    """Redirect the user to the Google authorization endpoint.

    We build the URL ourselves rather than pulling in a third-party library
    because the workspace environment does not allow installing new packages.

    Requires a ``state`` query parameter generated by the GUI (see
    ``_OAUTH_STATE_PATTERN`` for why).
    """
    state = _require_oauth_state(request.query_params.get("state"))
    redirect_uri = request.url_for("auth_google")
    params = {
        "client_id": _settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        # offline access allows us to refresh tokens, but not strictly
        # necessary for a simple login flow.
        "access_type": "offline",
        "prompt": "consent",
        # Google returns this unchanged to /auth/google.
        "state": state,
    }
    location = GOOGLE_AUTH_URL + "?" + urlencode(params)
    return RedirectResponse(location)


@app.get("/auth/google")
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def auth_google(request: Request, session: Session = Depends(get_session)):
    """OAuth callback endpoint that handles Google's authorization code.

    The handler:
    1. reads ``code`` and ``state`` from query parameters
    2. exchanges it for an access token at Google's token endpoint
    3. fetches the user's profile from the OpenID Connect userinfo API
    4. creates/looks up a local ``User`` record and issues our own JWT
    5. redirects to the GUI's /auth/callback page with the token and the
       ``state`` in the URL fragment, so the GUI can confirm that it started
       this login (see ``_OAUTH_STATE_PATTERN``)
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    state = _require_oauth_state(request.query_params.get("state"))

    # exchange code for tokens
    token_resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": request.url_for("auth_google"),
            "client_id": _settings.GOOGLE_CLIENT_ID,
            "client_secret": _settings.GOOGLE_CLIENT_SECRET,
        },
        headers={"Accept": "application/json"},
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch token")
    tok = token_resp.json()

    access_token = tok.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token response missing access_token")

    # use the access token to fetch user information
    userinfo_resp = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    user_info = userinfo_resp.json()
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Unable to retrieve email")

    user = get_by_username(session, email)
    if not user:
        random_password = secrets.token_urlsafe(16)
        full_name = user_info.get("name")
        user = create_user(session, username=email, password=random_password, full_name=full_name)

    access_token_inner = encode_token(data={"sub": user.username})
    # The token goes in the URL fragment (after "#"), which browsers never send
    # to servers, so it doesn't end up in access logs or Referer headers. The
    # dedicated /auth/callback page is the only place the GUI accepts a token.
    fragment = urlencode({"access_token": access_token_inner, "token_type": "bearer", "state": state})
    gui_url = f"{_settings.GUI_URL}auth/callback#{fragment}"
    return RedirectResponse(gui_url)


if __name__ == "__main__":
    # For use within Visual Studio Code debugging.
    # https://fastapi.tiangolo.com/tutorial/debugging/#run-your-code-with-your-debugger

    uvicorn.run(app, host="0.0.0.0", port=8000)
