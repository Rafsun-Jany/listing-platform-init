import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    value = os.environ.get("DATABASE_URL", "")
    if not value:
        raise RuntimeError("DATABASE_URL must be configured")
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    url = url or database_url()
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    from .main import session_factory

    with session_factory() as session:
        yield session

