"""Shared pytest fixtures. pytest loads this file automatically for every test module.

Tests run against their OWN database (`<dev database>_test`, e.g. `mgpa_test`) in the same
Postgres server, so they never see or touch real data. It is created and migrated before the
app is imported, because the app creates its database engine from DATABASE_URL at import time.
"""

from collections.abc import Iterator

from mgpa_backend.testing import use_test_database

use_test_database()

# Imported only now, so the engine is created for the test database.
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from mgpa_backend.db import engine, get_db  # noqa: E402
from mgpa_backend.main import app  # noqa: E402


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
