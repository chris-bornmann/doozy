from typing import Optional

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    GUI_URL: str = "http://localhost:5173/"

    ANTHROPIC_API_KEY: Optional[str] = None

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@doozy.app"
    SMTP_VALIDATE_CERTS: bool = True
    VERIFICATION_EXPIRE_MINUTES: int = 15
    VERIFICATION_URL: str = "http://localhost:8000/"

    model_config: SettingsConfigDict = SettingsConfigDict(env_file=find_dotenv())
