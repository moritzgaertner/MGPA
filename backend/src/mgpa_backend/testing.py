"""Test support shared by the backend and pipelines test suites (not used at runtime)."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from mgpa_backend.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def use_test_database() -> str:
    """Point DATABASE_URL at `<dev database>_test`, create it if needed, and migrate it.

    Must run before anything imports `mgpa_backend.db` (the engine is created at import time).
    Tests then never see or touch the real data. Returns the test database URL.
    """
    dev_url = make_url(get_settings().database_url)
    if dev_url.database and dev_url.database.endswith("_test"):
        test_url = dev_url  # already pointing at a test database
    else:
        test_url = dev_url.set(database=f"{dev_url.database}_test")

    admin_dsn = dev_url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{test_url.database}"')

    url = test_url.render_as_string(hide_password=False)
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    subprocess.run(  # noqa: S603  (fixed command, no user input)
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    return url
