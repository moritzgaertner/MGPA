"""Application settings, read from environment variables (and the repo-root .env file locally)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Locally the backend runs from backend/, so the shared .env lives one level up.
    # In Docker, values come from real environment variables, which always take precedence.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str


@lru_cache
def get_settings() -> Settings:
    """Return the settings, created once and then reused (cached)."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
