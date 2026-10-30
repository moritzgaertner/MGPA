"""Application settings, read from environment variables (and the repo-root .env file locally)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Locally the backend runs from backend/, so the shared .env lives one level up.
    # In Docker, values come from real environment variables, which always take precedence.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str

    # SecretStr hides the value in logs and error messages (prints as '**********').
    anthropic_api_key: SecretStr
    # Never hardcoded: which Claude model the chat agent uses, e.g. "claude-haiku-5-5".
    anthropic_model: str
    # How much the model thinks before answering; "low" keeps chat fast and cheap.
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"

    # Summarize older messages once a chat turn's input exceeds this many tokens.
    summary_trigger_tokens: int = 8_000
    # How many of the most recent messages always stay word for word.
    summary_keep_messages: int = 6


@lru_cache
def get_settings() -> Settings:
    """Return the settings, created once and then reused (cached)."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
