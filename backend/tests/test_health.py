import pytest
from fastapi.testclient import TestClient

from mgpa_backend.config import Settings
from mgpa_backend.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_reaches_database() -> None:
    # Needs a running Postgres (docker compose locally, service container in CI).
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # ignore any local .env

    assert settings.database_url == "postgresql+psycopg://u:p@localhost:5432/db"
