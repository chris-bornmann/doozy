# Overview

The intention is to provide three layers:
1. Routers - the FastAPI handlers.  In "src/routers".
2. Business Logic - All the goofy domain specific chcks.  In "src/service".
3. Database - Wrappers around DB calls.

The lines are more fluid than I'd like.  For example,
* Sometimes the busines logic does a bunch of database work.
* Sometimes the business logic returns an HTTPException.
* Sometimes the DB code performs business logic checks.

Sue me.

# Setup

## Initialize a new DB.
uv run python3 src/cli/main.py db create --seed
uv run python3 src/cli/main.py db blitz

## When using Postgres
psql -h db -p 5432 -U doozy
\d : Show tables


----

Install UV for package management -
curl -LsSf https://astral.sh/uv/install.sh | sudo sh

Create the project.
mkdir ~/dev/doozy/server
cd ~/dev/doozy/server
uv init --name doozy

This creates an empty README.md, a main.py, a pyproject.toml, a .gitignore, and a .git repo.

WHAT DO ALL THESE DO DIFFERENTLY?
      --bare
          Only create a `pyproject.toml`
      --package
          Set up the project to be built as a Python package
      --no-package
          Do not set up the project to be built as a Python package
      --app
          Create a project for an application
      --lib
          Create a project for a library
      --script
          Create a script
      --build-backend <BUILD_BACKEND>
          Initialize a build-backend of choice for the project [env:
          UV_INIT_BUILD_BACKEND=] [possible values: uv, hatch, flit, pdm, poetry,
          setuptools, maturin, scikit]
      --author-from <AUTHOR_FROM>
          Fill in the `authors` field in the `pyproject.toml` [possible values:
          auto, git, none]
      --no-pin-python
          Do not create a `.python-version` file for the project
      --no-workspace
          Avoid discovering a workspace and create a standalone project


# Add SqlModel -
```
uv add sqlmodel
```
This also adds SqlAlchemy, Pydantic, etc.

# Add FastAPI -
```
uv add "fastapi[standard]"
uv add fastapi-pagination
```

# Add PyJwt and pwdlib (both used for authentication)
```
uv add pyjwt
uv add "pyjwt[crypto]"
uv add "pwdlib[argon2]"
```

# Add Pydantic Settings, so that we can use a .env file.
```
uv add pydantic_settings
```

# Add Ruff, and Ty, but only to dev environments.
```
uv add --dev ruff
uv add --dev ty
uv run ruff check
uv run ty check
```

# Run It
```
uv run fastapi dev src/app/main.py
export PYTHONPATH=/Users/cbb/dev/doozy/server/src

Once poe is configured with...

[tool.poe.tasks]
run       = "uvicorn app.main:app --reload --app-dir src"

uv run poe run --host 0.0.0.0
```

# Add a CLI
```
uv add --dev typer
uv add --dev prettytable

```

# Run the app...
uv run fastapi dev src/app/main.py

## Google OAuth2 login

1. Obtain client credentials from the Google API console and set
   ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` in your environment or
   in the project's ``.env`` file.
2. Set ``GUI_URL`` to the web GUI's address (default ``http://localhost:5173/``)
   and add the GUI's origin to ``CORS_ORIGINS`` (see *Configuration* below).
3. Start the server and the GUI, and use "Continue with Google" on the GUI's
   login page. The GUI generates a random ``state`` value and calls
   ``/login/google?state=...``, which redirects to Google. Google sends the
   user back to ``/auth/google``, which redirects to the GUI's
   ``/auth/callback`` page with ``access_token``, ``token_type`` and the same
   ``state`` in the URL fragment. The GUI accepts the token only if ``state``
   matches the one it generated, which protects against login CSRF.

``/login/google`` and ``/auth/google`` both return ``400`` without a valid
``state`` (16–128 URL-safe characters), so visiting ``/login/google`` directly
no longer works. Sign-in only requests the ``openid email profile`` scopes,
with no offline access, so Google issues no long-lived refresh token.

The resulting ``access_token`` is used with the standard
``Authorization: Bearer ...`` header, exactly as with the username/password
``/token`` endpoint.

> **Error responses from `/token`**
>
> If a username/password login fails the endpoint now returns a proper
> `401` status with a JSON body (`{"detail": "Incorrect username or password"}`).
> The `WWW-Authenticate` header has been removed so that browsers and client
> pages see the response body instead of surfacing a generic "NetworkError"
> message.

The rest of the API doesn't distinguish between Google accounts and regular
users; both are issued the same JWTs on successful authentication.

## Configuration: allowed browser origins (CORS)

Browsers only let a web page call this API from JavaScript if the page's
origin is listed in ``CORS_ORIGINS``. Each environment sets its own list, in
its ``.env`` file (``.env`` locally, ``.env.compose`` for Docker Compose) or as
an environment variable in production. The value is comma-separated:

```
# Production
CORS_ORIGINS=https://doozy.example.com

# Local development, plus access from another machine (e.g. over Tailscale)
CORS_ORIGINS=http://localhost:5173,http://localhost:8080,http://100.104.51.111:5173
```

- Each entry is ``scheme://host[:port]`` with no path or trailing slash (CORS
  compares origins exactly). The server refuses to start on a malformed entry,
  and ``*`` is not allowed.
- If ``CORS_ORIGINS`` is not set, only local development is allowed:
  ``http://localhost:5173`` (Vite dev server) and ``http://localhost:8080``
  (Docker Compose GUI).
- Setting it *replaces* that default, so list every origin the environment needs.
- The test suite sets its own value in ``src/conftest.py``.
