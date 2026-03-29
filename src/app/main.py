from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi_pagination import add_pagination
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from db.main import db_create, get_session
from app.middleware import LoggingMiddleware, TimingMiddleware
from routers import items, users
from util.security import authenticate_user, encode_token, Token

# configuration and oauth-related helpers
from app.config import Settings

# helper imports for user creation in google flow
import secrets
from db.users import get_by_username, create_user
from util.security import get_password_hash
from sqlmodel import Session
import httpx
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode


@asynccontextmanager
async def lifespan(app: FastAPI):
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


# load settings (reads environment or .env file)
settings = Settings()

# make sure the two required variables are present; we will use them a
# couple of times later when constructing URLs/requests.
if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in the"
        " environment to use Google authentication"
    )

# OAuth endpoints used by the Google OpenID Connect flow
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

app = FastAPI(
    title="Doozy",
    description="The Doozy API",
    version="0.0.1",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


app.add_middleware(LoggingMiddleware, file_name="/tmp/doozy.log")
app.add_middleware(TimingMiddleware)

app.include_router(items.router)
app.include_router(users.router)

# Define allowed origins.  Eventually this should include an actual
# web hosted site where the GUI is served from.
origins = [
    "http://localhost:5173",  # Local dev/test.
]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization"])

# Permanent URLs too...
app.include_router(items.router, prefix="/v1/items", tags=["items", "v1"])
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
async def login(
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


# oauth2 endpoints for Google ------------------------------------------------
@app.get("/login/google")
async def login_google(request: Request):
    """Redirect the user to the Google authorization endpoint.

    We build the URL ourselves rather than pulling in a third-party library
    because the workspace environment does not allow installing new packages.
    """
    redirect_uri = request.url_for("auth_google")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        # offline access allows us to refresh tokens, but not strictly
        # necessary for a simple login flow.
        "access_type": "offline",
        "prompt": "consent",
    }
    location = GOOGLE_AUTH_URL + "?" + urlencode(params)
    return RedirectResponse(location)


@app.get("/auth/google")
async def auth_google(request: Request, session: Session = Depends(get_session)) -> Token:
    """OAuth callback endpoint that handles Google's authorization code.

    The handler:
    1. reads ``code`` from query parameters
    2. exchanges it for an access token at Google's token endpoint
    3. fetches the user's profile from the OpenID Connect userinfo API
    4. creates/looks up a local ``User`` record and issues our own JWT
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    # exchange code for tokens
    token_resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": request.url_for("auth_google"),
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
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
    return Token(access_token=access_token_inner, token_type="bearer")


if __name__ == "__main__":
    # For use within Visual Studio Code debugging.
    # https://fastapi.tiangolo.com/tutorial/debugging/#run-your-code-with-your-debugger

    uvicorn.run(app, host="0.0.0.0", port=8000)
