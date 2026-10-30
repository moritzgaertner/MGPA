"""Shared pytest fixtures. pytest loads this file automatically for every test module."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mgpa_backend.db import engine, get_db
from mgpa_backend.main import app


@pytest.fixture
def db() -> Iterator[Session]:
    """A session inside a transaction that is always rolled back, so tests leave no data.

    Commits inside the test only release a savepoint; the outer transaction is undone at the end.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """HTTP test client whose endpoints use the rolled-back test session instead of a real one."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
