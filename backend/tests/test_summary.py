"""Tests for the rolling conversation summary. Both Claude agents are replaced by fakes."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent
from mgpa_backend.config import get_settings
from mgpa_backend.models import Conversation, Message, MessageRole
from mgpa_backend.summary import fold_cutoff, get_summarizer

U, A = MessageRole.USER, MessageRole.ASSISTANT

chat_requests: list[list[ModelMessage]] = []
summary_requests: list[list[ModelMessage]] = []


async def fake_chat(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
    chat_requests.append(messages)
    yield "ok"


def fake_summary(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    summary_requests.append(messages)
    return ModelResponse(parts=[TextPart(content="- User trains 3x per week")])


def broken_summary(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise RuntimeError("simulated outage")


@pytest.fixture
def fakes() -> Iterator[None]:
    chat_requests.clear()
    summary_requests.clear()
    with (
        get_agent().override(model=FunctionModel(stream_function=fake_chat)),
        get_summarizer().override(model=FunctionModel(fake_summary)),
    ):
        yield


@pytest.fixture
def always_summarize(monkeypatch: pytest.MonkeyPatch) -> None:
    """Threshold 0 = every turn is "too long"; keep the last 4 messages verbatim."""
    monkeypatch.setattr(get_settings(), "summary_trigger_tokens", 0)
    monkeypatch.setattr(get_settings(), "summary_keep_messages", 4)


def seed_conversation(db: Session, pairs: int) -> Conversation:
    messages = []
    for i in range(1, pairs + 1):
        messages += [
            Message(role=U, content=f"question {i}"),
            Message(role=A, content=f"answer {i}"),
        ]
    conversation = Conversation(messages=messages)
    db.add(conversation)
    db.commit()
    return conversation


# --- fold_cutoff: pure logic, no database ------------------------------------------------------


def roles(*rs: MessageRole) -> list[Message]:
    return [Message(role=r, content="x") for r in rs]


def test_cutoff_keeps_last_messages() -> None:
    assert fold_cutoff(roles(U, A, U, A, U, A, U, A), keep=4) == 4


def test_cutoff_moves_forward_so_kept_part_starts_with_user() -> None:
    # keep=3 would start the kept part with an assistant message -> fold one more
    assert fold_cutoff(roles(U, A, U, A, U, A), keep=3) == 4


def test_cutoff_returns_zero_when_too_little_to_fold() -> None:
    assert fold_cutoff(roles(U, A, U, A), keep=4) == 0  # nothing older than the kept part
    assert fold_cutoff(roles(U, U, A, U, A), keep=4) == 0  # would fold just one message


# --- end to end through POST /chat -------------------------------------------------------------


@pytest.mark.usefixtures("fakes")
def test_no_summary_below_threshold(client: TestClient, db: Session) -> None:
    conversation = seed_conversation(db, pairs=5)

    client.post("/chat", json={"conversation_id": conversation.id, "message": "next"})

    db.refresh(conversation)
    assert conversation.summary is None
    assert summary_requests == []


@pytest.mark.usefixtures("fakes", "always_summarize")
def test_long_chat_is_summarized_and_next_turn_uses_summary(
    client: TestClient, db: Session
) -> None:
    conversation = seed_conversation(db, pairs=5)  # 10 messages

    # Turn adds 2 more (12). Keep 4 -> fold the first 8 (= question/answer 1-4).
    client.post("/chat", json={"conversation_id": conversation.id, "message": "question 6"})

    db.refresh(conversation)
    assert conversation.summary == "- User trains 3x per week"
    folded = sorted(m.id for m in conversation.messages)[:8]
    assert conversation.summarized_until_id == folded[-1]
    assert "question 1" in str(summary_requests[-1])  # old messages went to the summarizer
    assert "question 5" not in str(summary_requests[-1])  # recent ones did not

    # Next turn: Claude gets the summary in the system prompt + only the recent messages.
    client.post("/chat", json={"conversation_id": conversation.id, "message": "question 7"})

    sent = chat_requests[-1]
    sent_text = str(sent)
    assert "question 1" not in sent_text and "answer 4" not in sent_text
    assert "question 5" in sent_text and "question 6" in sent_text
    last = sent[-1]
    assert isinstance(last, ModelRequest) and last.instructions
    assert "- User trains 3x per week" in last.instructions

    # Nothing was deleted: the API still returns every message.
    # (In tests all requests share one session; drop its cached message list first.
    # In production every request gets a fresh session, so this cannot happen there.)
    db.expire_all()
    stored = client.get(f"/conversations/{conversation.id}").json()["messages"]
    assert len(stored) == 14


@pytest.mark.usefixtures("always_summarize")
def test_failed_summary_does_not_break_the_chat(client: TestClient, db: Session) -> None:
    conversation = seed_conversation(db, pairs=5)
    with (
        get_agent().override(model=FunctionModel(stream_function=fake_chat)),
        get_summarizer().override(model=FunctionModel(broken_summary)),
    ):
        response = client.post(
            "/chat", json={"conversation_id": conversation.id, "message": "next"}
        )

    assert "event: done" in response.text
    db.refresh(conversation)
    assert conversation.summary is None
