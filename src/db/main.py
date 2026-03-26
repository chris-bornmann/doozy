
from sqlmodel import create_engine, Session, SQLModel

from app.config import Settings


settings = Settings()
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def db_create():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
