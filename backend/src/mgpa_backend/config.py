"""Application settings, read from environment variables (and the repo-root .env file locally)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/mgpa_backend/config.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # The shared .env lives in the repo root (the backend and the Dagster pipelines both read it).
    # In Docker, values come from real environment variables, which always take precedence.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str

    # SecretStr hides the value in logs and error messages (prints as '**********').
    anthropic_api_key: SecretStr
    # Never hardcoded: which Claude model the chat agent uses, e.g. "claude-haiku-5-5".
    anthropic_model: str
    # How much the model thinks before answering; "low" keeps chat fast and cheap.
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"

    # Login (single user). Set with `uv run python -m mgpa_backend.auth` — it stores only an
    # argon2 hash of the password, never the password itself.
    auth_username: str
    auth_password_hash: SecretStr
    # Signs the session cookie; anyone with it could forge a login, so keep it secret.
    session_secret: SecretStr
    session_max_age_days: int = 30

    # Embeddings for the knowledge base (Voyage AI). Without a key, ingestion and search fail
    # with a clear error; everything else keeps working.
    voyage_api_key: SecretStr | None = None
    # Never hardcoded: e.g. "voyage-4". Must produce EMBEDDING_DIMENSIONS-sized vectors.
    embedding_model: str
    # Where uploaded documents are stored. Shared by the API (writes) and Dagster (reads).
    documents_dir: Path = REPO_ROOT / "data" / "documents"

    # Langfuse tracing (observability). Leave the keys empty to disable tracing (tests, CI).
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"  # EU region
    # Shown as "environment" in Langfuse, so local and production traces can be told apart.
    app_env: str = "development"

    # The owner's time zone: "today"/"yesterday" in the chat and training dates use it.
    timezone: str = "Europe/Berlin"

    # Summarize older messages once a chat turn's input exceeds this many tokens.
    summary_trigger_tokens: int = 8_000
    # How many of the most recent messages always stay word for word.
    summary_keep_messages: int = 6


@lru_cache
def get_settings() -> Settings:
    """Return the settings, created once and then reused (cached)."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
