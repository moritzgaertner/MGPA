"""The search_knowledge tool inside a chat turn — fake model, fake embeddings, real pgvector."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent, run_knowledge_search
from mgpa_backend.config import get_settings
from mgpa_backend.knowledge.embeddings import EmbeddingsNotConfiguredError
from mgpa_backend.knowledge.ingest import ingest_document
from mgpa_backend.knowledge.search import SearchHit
from mgpa_backend.routers import chat as chat_router
from tests.fakes import FakeEmbedder
from tests.test_chat_api import parse_sse

PLAN = b"# Plan\n\n## Day A\n\nChest press.\n\n## Day B\n\nLeg press, 4 sets of 10 at 140 kg.\n"
tool_results: list[str] = []


async def model_that_searches(
    messages: list[ModelMessage], info: AgentInfo
) -> AsyncIterator[str | DeltaToolCalls]:
    """1st call: some text, THEN a tool call (the case run_stream would cut off).
    2nd call: answer using the tool result."""
    last = messages[-1]
    returns = (
        [p for p in last.parts if isinstance(p, ToolReturnPart)]
        if isinstance(last, ModelRequest)
        else []
    )
    if not returns:
        yield "Let me check your plan. "
        yield {0: DeltaToolCall(name="search_knowledge", json_args='{"query": "leg press day B"}')}
        return
    tool_results.append(str(returns[0].content))
    yield "Day B: leg press, 4 × 10 at 140 kg *(Source: plan.md › Plan › Day B)*"


@pytest.fixture
def knowledge(
    client: TestClient, db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """One ingested document + fake embeddings for queries + the fake model."""
    monkeypatch.setattr(get_settings(), "documents_dir", tmp_path)
    embedder = FakeEmbedder()
    monkeypatch.setattr(chat_router, "get_embedder", lambda: embedder)
    response = client.post("/documents", files={"file": ("plan.md", PLAN, "text/markdown")})
    ingest_document(db, response.json()["id"], embedder)
    tool_results.clear()
    with get_agent().override(model=FunctionModel(stream_function=model_that_searches)):
        yield


@pytest.mark.usefixtures("knowledge")
def test_chat_searches_knowledge_and_streams_tool_event(client: TestClient) -> None:
    events = parse_sse(client.post("/chat", json={"message": "What's on day B?"}).text)

    names = [name for name, _ in events]
    assert names[0] == "start" and names[-1] == "done"
    assert ("tool", {"name": "search_knowledge", "args": {"query": "leg press day B"}}) in events

    # The tool really ran and returned the right section with its source.
    assert "Source: plan.md › Plan › Day B" in tool_results[0]
    assert "140 kg" in tool_results[0]

    # Text before AND after the tool call reached the client.
    text = "".join(data["text"] for name, data in events if name == "delta")
    assert text.startswith("Let me check your plan.")
    assert "(Source: plan.md › Plan › Day B)" in text


def test_tool_explains_missing_configuration() -> None:
    async def not_configured(query: str) -> list[SearchHit]:
        raise EmbeddingsNotConfiguredError("no key")

    async def nothing(query: str) -> list[SearchHit]:
        return []

    assert "not configured" in asyncio.run(run_knowledge_search(not_configured, "x"))
    assert "No relevant passages" in asyncio.run(run_knowledge_search(nothing, "x"))
    assert "not available" in asyncio.run(run_knowledge_search(None, "x"))
