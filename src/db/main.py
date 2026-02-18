
from sqlmodel import create_engine, Session, SQLModel

# !@# Temporary Kludge!
from db.cli import create


database_url = "sqlite:///database.db"
connect_args = {"check_same_thread": False}
engine = create_engine(database_url, connect_args=connect_args)

def db_create():
    create()


def get_session():
    with Session(engine) as session:
        yield session
