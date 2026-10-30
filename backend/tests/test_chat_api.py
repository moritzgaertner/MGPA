"""Tests for POST /chat. Claude is replaced by a fake model, so no API calls and no costs."""

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent
from mgpa_backend.models import Conversation, Message, MessageRole


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Turn a raw SSE response body into [(event, data), ...]."""
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


# Every model request the fake model received, so tests can inspect the history sent.
received: list[list[ModelMessage]] = []


async def fake_stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
    received.append(messages)
    for chunk in ["Hello", ", ", "world!"]:
        yield chunk


async def failing_stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
    raise RuntimeError("simulated API outage")
    yield ""  # unreachable, but makes this an async generator


@pytest.fixture
def fake_model() -> Iterator[None]:
    received.clear()
    with get_agent().override(model=FunctionModel(stream_function=fake_stream)):
        yield


@pytest.mark.usefixtures("fake_model")
def test_chat_streams_answer_and_saves_both_messages(client: TestClient, db: Session) -> None:
    response = client.post("/chat", json={"message": "Hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "start" and names[-1] == "done"
    assert "".join(data["text"] for name, data in events if name == "delta") == "Hello, world!"

    conversation_id = events[0][1]["conversation_id"]
    messages = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    ).all()
    assert [(m.role, m.content) for m in messages] == [
        (MessageRole.USER, "Hi"),
        (MessageRole.ASSISTANT, "Hello, world!"),
    ]
    assert events[-1][1]["message_id"] == messages[1].id


@pytest.mark.usefixtures("fake_model")
def test_chat_sends_previous_messages_as_history(client: TestClient, db: Session) -> None:
    conversation = Conversation(
        messages=[
            Message(role=MessageRole.USER, content="My name is Alex."),
            Message(role=MessageRole.ASSISTANT, content="Nice to meet you, Alex!"),
        ]
    )
    db.add(conversation)
    db.commit()

    client.post("/chat", json={"conversation_id": conversation.id, "message": "Who am I?"})

    sent_text = str(received[-1])
    assert "My name is Alex." in sent_text
    assert "Nice to meet you, Alex!" in sent_text
    assert "Who am I?" in sent_text


def test_chat_model_error_streams_error_and_keeps_user_message(
    client: TestClient, db: Session
) -> None:
    with get_agent().override(model=FunctionModel(stream_function=failing_stream)):
        response = client.post("/chat", json={"message": "Hi"})

    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["start", "error"]
    assert "simulated" not in response.text  # internal details are not leaked

    conversation_id = events[0][1]["conversation_id"]
    roles = db.scalars(select(Message.role).where(Message.conversation_id == conversation_id)).all()
    assert roles == [MessageRole.USER]


def test_chat_unknown_conversation_returns_404(client: TestClient) -> None:
    response = client.post("/chat", json={"conversation_id": 999_999, "message": "Hi"})

    assert response.status_code == 404


def test_chat_rejects_empty_message(client: TestClient) -> None:
    assert client.post("/chat", json={"message": ""}).status_code == 422
