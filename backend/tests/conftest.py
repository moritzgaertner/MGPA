"""Shared pytest fixtures. pytest loads this file automatically for every test module.

Tests run against their OWN database (`<dev database>_test`, e.g. `mgpa_test`) in the same
Postgres server, so they never see or touch real data. It is created and migrated automatically
before the first test. This has to happen before the app is imported, because the app creates its
database engine from DATABASE_URL at import time.
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from mgpa_backend.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _use_test_database() -> None:
    dev_url = make_url(get_settings().database_url)
    test_url = dev_url.set(database=f"{dev_url.database}_test")

    # Create the test database if needed (connect to the always-present "postgres" database).
    admin_dsn = dev_url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{test_url.database}"')

    # Point the app (and Alembic) at the test database, then bring its schema up to date.
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    subprocess.run(  # noqa: S603  (fixed command, no user input)
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
    )


_use_test_database()

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
