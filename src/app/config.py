from typing import Optional

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

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
