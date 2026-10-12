import re
from functools import lru_cache
from typing import Annotated, Any, Optional

from dotenv import find_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# A browser origin: scheme and host (and optional port), with no path or
# trailing slash. CORS compares origins as exact strings, so something like
# "https://doozy.example.com/" would silently never match.
_ORIGIN_PATTERN = re.compile(r"^https?://[^/\s]+$")

class Settings(BaseSettings):

    # Optional here *should* mean the value really is optional - that the code will
    # work with a None value.  That's not what it means today...  Today it just means
    # that we aren't setting a default here, because the only usable values still
    # need to be secret.

    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = "sqlite:///database.db"

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    GUI_URL: str = "http://localhost:5173/"

    # Browser origins allowed to call this API from JavaScript (CORS). Each
    # environment (dev, test, prod, ...) sets its own list, as a comma-separated
    # value in its .env file or environment, e.g.:
    #   CORS_ORIGINS=https://doozy.example.com,https://www.doozy.example.com
    # Any other site's JavaScript is refused by the browser. The default only
    # covers local development: the Vite dev server and local Docker (nginx).
    # NoDecode: read the raw string and split it in _parse_cors_origins below,
    # rather than requiring a JSON list.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LOGFIRE_TOKEN: Optional[str] = None

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@doozy.app"
    SMTP_VALIDATE_CERTS: bool = True
    VERIFICATION_EXPIRE_MINUTES: int = 15
    VERIFICATION_URL: str = "http://localhost:8000/"

    # Rate limiting — SlowAPI format: "N/period" e.g. "100/minute", "10/second"
    # Override any of these in .env to tune limits for your deployment.
    RATE_LIMIT_DEFAULT: str = "60/minute"   # general authenticated endpoints
    RATE_LIMIT_AUTH: str = "5/minute"       # login, register, OAuth, email verify
    RATE_LIMIT_AI: str = "6/minute"         # AI endpoints (direct Anthropic/OpenAI cost)
    RATE_LIMIT_HEALTH: str = "60/minute"    # health check (unauthenticated)

    model_config: SettingsConfigDict = SettingsConfigDict(env_file=find_dotenv())

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(
        cls,
        value: Any,
    ) -> list[str]:
        """Split a comma-separated CORS_ORIGINS value and check each origin.

        Fails at startup on a malformed entry instead of silently blocking the
        GUI. "*" (allow every site) is refused on purpose: the API carries
        users' login tokens, so callers should always be listed explicitly.
        """
        origins = value.split(",") if isinstance(value, str) else list(value)
        origins = [origin.strip() for origin in origins if origin.strip()]
        for origin in origins:
            if not _ORIGIN_PATTERN.fullmatch(origin):
                raise ValueError(
                    f"Invalid CORS origin {origin!r}: use scheme://host[:port] with no "
                    "path or trailing slash, e.g. https://doozy.example.com"
                )
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
