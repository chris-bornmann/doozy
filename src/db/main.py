
import logfire
from sqlmodel import create_engine, Session, SQLModel

from app.config import get_settings


_settings = get_settings()
# check_same_thread is SQLite-only; omit it for other drivers
_is_sqlite = _settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(_settings.DATABASE_URL, connect_args=_connect_args)
logfire.instrument_sqlalchemy(engine=engine)


def db_create():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
