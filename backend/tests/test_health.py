import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "some-model-id")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # ignore any local .env

    assert settings.database_url == "postgresql+psycopg://u:p@localhost:5432/db"
    assert settings.anthropic_model == "some-model-id"
    assert settings.anthropic_effort == "low"  # default
    # The key is wrapped so it never shows up in logs or error messages by accident.
    assert "sk-ant-test" not in repr(settings)
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-test"


def test_settings_require_api_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
