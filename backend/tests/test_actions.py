"""Human-in-the-loop: the assistant proposes, the user confirms or discards."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, RetryPromptPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent
from mgpa_backend.models import Action, ActionStatus, Note
from tests.test_chat_api import parse_sse

tool_returns: list[str] = []


def last_parts(messages: list[ModelMessage]) -> list[object]:
    last = messages[-1]
    return list(last.parts) if isinstance(last, ModelRequest) else []


async def model_that_proposes(
    messages: list[ModelMessage], info: AgentInfo
) -> AsyncIterator[str | DeltaToolCalls]:
    """Proposes a note on the first call; on a retry prompt (invalid args) fixes the title."""
    parts = last_parts(messages)
    feedback = [str(p.content) for p in parts if isinstance(p, ToolReturnPart | RetryPromptPart)]
    retried = any("Invalid note" in text for text in feedback)
    if feedback and not retried:
        tool_returns.append(feedback[0])
        yield "Ready to confirm."
        return
    title = "Shopping" if retried or "short" in str(messages[0]) else "x" * 201
    args = f'{{"title": "{title}", "content": "Oat milk, bananas"}}'
    yield {0: DeltaToolCall(name="propose_note", json_args=args)}


@pytest.fixture
def proposing_model() -> Iterator[None]:
    tool_returns.clear()
    with get_agent().override(model=FunctionModel(stream_function=model_that_proposes)):
        yield


def chat(client: TestClient, message: str) -> list[tuple[str, dict[str, object]]]:
    return parse_sse(client.post("/chat", json={"message": message}).text)


def proposed_action_id(events: list[tuple[str, dict[str, object]]]) -> int:
    action = next(data["action"] for name, data in events if name == "proposal")
    assert isinstance(action, dict)
    return int(action["id"])


@pytest.mark.usefixtures("proposing_model")
def test_proposal_is_streamed_and_nothing_is_saved_yet(client: TestClient, db: Session) -> None:
    notes_before = db.query(Note).count()

    events = chat(client, "short: note my shopping list")

    proposals = [data for name, data in events if name == "proposal"]
    assert len(proposals) == 1
    action = proposals[0]["action"]
    assert isinstance(action, dict)
    assert action["status"] == "proposed"
    assert action["label"] == "Save note “Shopping”"
    assert db.query(Note).count() == notes_before  # not written before confirmation
    assert "Nothing is saved until they confirm" in tool_returns[0]


@pytest.mark.usefixtures("proposing_model")
def test_proposal_is_attached_to_the_answer(client: TestClient, db: Session) -> None:
    events = chat(client, "short: note it")
    conversation_id = events[0][1]["conversation_id"]

    db.expire_all()
    messages = client.get(f"/conversations/{conversation_id}").json()["messages"]

    assistant = messages[-1]
    assert assistant["role"] == "assistant"
    assert [a["label"] for a in assistant["actions"]] == ["Save note “Shopping”"]
    assert messages[0]["actions"] == []  # the user message has none


@pytest.mark.usefixtures("proposing_model")
def test_confirm_executes_the_action_once(client: TestClient, db: Session) -> None:
    action_id = proposed_action_id(chat(client, "short: note it"))

    confirmed = client.post(f"/actions/{action_id}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["result_summary"] == "Note “Shopping” saved"
    action = db.get_one(Action, action_id)
    note = db.get_one(Note, action.result_id)
    assert (note.title, note.content, note.is_pinned) == ("Shopping", "Oat milk, bananas", False)

    again = client.post(f"/actions/{action_id}/confirm")
    assert again.status_code == 409  # cannot create the note twice


@pytest.mark.usefixtures("proposing_model")
def test_reject_writes_nothing(client: TestClient, db: Session) -> None:
    notes_before = db.query(Note).count()
    action_id = proposed_action_id(chat(client, "short: note it"))

    rejected = client.post(f"/actions/{action_id}/reject")

    assert rejected.json()["status"] == "rejected"
    assert db.query(Note).count() == notes_before
    assert client.post(f"/actions/{action_id}/confirm").status_code == 409


@pytest.mark.usefixtures("proposing_model")
def test_invalid_proposal_makes_the_model_retry(client: TestClient, db: Session) -> None:
    events = chat(client, "note it")  # first attempt uses a 201-character title

    proposals = [data for name, data in events if name == "proposal"]
    assert len(proposals) == 1  # only the corrected one was stored
    stored = db.scalars(select(Action).where(Action.status == ActionStatus.PROPOSED)).all()
    assert all(len(a.payload["title"]) <= 200 for a in stored)


def test_unknown_action_returns_404(client: TestClient) -> None:
    assert client.post("/actions/999999/confirm").status_code == 404
