from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    model_config: SettingsConfigDict = SettingsConfigDict(env_file=find_dotenv())
