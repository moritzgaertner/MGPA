"""Tracing of agent runs with Langfuse (via OpenTelemetry).

Pydantic AI emits OpenTelemetry spans for every agent run (prompt, response, tokens, timing,
tool calls); the Langfuse client collects them and sends them to Langfuse Cloud in the background.
Without Langfuse keys everything here is a no-op, so tests and CI never send data anywhere.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse, propagate_attributes
from pydantic_ai import Agent

from mgpa_backend.config import Settings

logger = logging.getLogger(__name__)

_client: Langfuse | None = None


def setup_tracing(settings: Settings, **client_options: Any) -> bool:
    """Start tracing if Langfuse keys are configured. Returns whether tracing is on.

    `client_options` are passed to the Langfuse client (tests use it to capture spans locally).
    """
    global _client
    if not settings.langfuse_public_key or settings.langfuse_secret_key is None:
        logger.info("Langfuse keys not set: tracing disabled")
        return False
    _client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        environment=settings.app_env,
        **client_options,
    )
    Agent.instrument_all()  # every Pydantic AI agent now emits spans
    logger.info("Langfuse tracing enabled (%s)", settings.langfuse_base_url)
    return True


def shutdown_tracing() -> None:
    """Send buffered spans and stop tracing (server shutdown)."""
    global _client
    if _client is None:
        return
    _client.flush()
    _client.shutdown()
    Agent.instrument_all(False)
    _client = None


@contextmanager
def traced(name: str, conversation_id: int, tags: list[str]) -> Iterator[None]:
    """Label all spans created inside this block: trace name, session (= conversation), tags.

    In Langfuse, the session groups every turn of one conversation into a single timeline.
    """
    if _client is None:
        yield
        return
    with propagate_attributes(
        trace_name=name, session_id=f"conversation-{conversation_id}", tags=tags
    ):
        yield
