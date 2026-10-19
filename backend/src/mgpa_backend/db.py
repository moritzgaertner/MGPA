"""Database connection: engine, session factory, declarative base and FastAPI dependency."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from mgpa_backend.config import get_settings

# Deterministic constraint names, so Alembic can find and change constraints later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of all ORM models. Its metadata is the registry of all tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# The engine manages a pool of open connections to Postgres.
# pool_pre_ping checks a connection before use, so a restarted database does not break requests.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# Factory that creates new sessions bound to the engine.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with SessionLocal() as session:
        yield session
