"""Tracing tests. Spans go to an in-memory exporter instead of Langfuse — no network, no keys."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from mgpa_backend import observability
from mgpa_backend.agent import get_agent, make_claude_model
from mgpa_backend.config import Settings


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "anthropic_api_key": "sk-ant-test",
        "anthropic_model": "test-model",
        **overrides,
    }
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


async def fake_stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
    yield "traced answer"


def test_anthropic_sdk_spans_are_disabled() -> None:
    # Pydantic AI already traces every model call; SDK spans on top would double-count cost.
    client = make_claude_model().client
    assert client.open_telemetry["traces"]["enabled"] is False


def test_tracing_is_off_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert observability.setup_tracing(make_settings()) is False


def test_chat_turn_is_traced_with_conversation_as_session(client: TestClient) -> None:
    exporter = InMemorySpanExporter()
    settings = make_settings(langfuse_public_key="pk-lf-test", langfuse_secret_key="sk-lf-test")
    assert observability.setup_tracing(settings, span_exporter=exporter) is True
    try:
        with get_agent().override(model=FunctionModel(stream_function=fake_stream)):
            body = client.post("/chat", json={"message": "Hi"}).text
    finally:
        observability.shutdown_tracing()  # flushes all spans into the exporter

    conversation_id = int(body.split('"conversation_id":')[1].split("}")[0])
    spans = exporter.get_finished_spans()
    assert spans, "the agent run produced no spans"
    attribute_values = [value for span in spans for value in (span.attributes or {}).values()]
    assert f"conversation-{conversation_id}" in attribute_values  # session = conversation
    assert "chat" in attribute_values  # trace name
    assert any("traced answer" in str(value) for value in attribute_values)  # output captured
