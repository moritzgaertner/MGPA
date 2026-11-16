"""Training tools in a chat turn: fake model, synthetic plan, real database."""

import json
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, RetryPromptPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent
from mgpa_backend.models import Exercise, TrainingSession
from mgpa_backend.training.importer import import_training, parse_context
from tests.test_chat_api import parse_sse
from tests.test_training import CONTEXT, ROWS

feedback: list[str] = []


def model_calling(
    tool: str, *argument_sets: dict[str, object]
) -> Callable[[list[ModelMessage], AgentInfo], AsyncIterator[str | DeltaToolCalls]]:
    """Fake model: calls `tool` with the next argument set until the tools stop complaining."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        last = messages[-1]
        parts = list(last.parts) if isinstance(last, ModelRequest) else []
        replies = [str(p.content) for p in parts if isinstance(p, ToolReturnPart | RetryPromptPart)]
        feedback.extend(replies)
        attempt = sum(1 for m in messages if isinstance(m, ModelRequest)) - 1
        if replies and not any("Unknown exercise" in r or "Invalid" in r for r in replies):
            yield "Done."
            return
        args = argument_sets[min(attempt, len(argument_sets) - 1)]
        yield {0: DeltaToolCall(name=tool, json_args=json.dumps(args))}

    return stream


@pytest.fixture(autouse=True)
def plan(db: Session) -> Iterator[None]:
    import_training(db, parse_context(CONTEXT), ROWS)
    feedback.clear()
    yield


def run(
    client: TestClient, tool: str, *args: dict[str, object]
) -> list[tuple[str, dict[str, object]]]:
    with get_agent().override(model=FunctionModel(stream_function=model_calling(tool, *args))):
        return parse_sse(client.post("/chat", json={"message": "log it"}).text)


def proposal(events: list[tuple[str, dict[str, object]]]) -> dict[str, object]:
    action = next(data["action"] for name, data in events if name == "proposal")
    assert isinstance(action, dict)
    return action


def test_training_log_resolves_aliases_and_default_sets(client: TestClient) -> None:
    events = run(
        client,
        "propose_training_log",
        {
            "date": "2026-03-15",
            "entries": [{"exercise": "tp", "weight": 65}, {"exercise": "SQ", "weight": 25}],
        },
    )

    action = proposal(events)
    payload = action["payload"]
    assert isinstance(payload, dict)
    assert [(e["exercise"], e["weight"], e["sets"]) for e in payload["entries"]] == [
        ("Test Press", 65.0, 3),
        ("Test Squat", 25.0, 2),  # this exercise usually has 2 sets
    ]
    assert payload["date"] == "2026-03-15"
    assert payload["focus"] == "Pushday"  # 1:1 tie -> first seen focus wins
    assert action["label"] == "Log training Pushday · 15.03.2026 (2 exercises)"


def test_confirmed_log_creates_session_and_follow_up_extends_it(
    client: TestClient, db: Session
) -> None:
    first = proposal(
        run(
            client,
            "propose_training_log",
            {"date": "2026-03-15", "entries": [{"exercise": "TP", "weight": 65}]},
        )
    )
    client.post(f"/actions/{first['id']}/confirm")
    second = proposal(
        run(
            client,
            "propose_training_log",
            {
                "date": "2026-03-15",
                "entries": [{"exercise": "Test Raise", "weight": 11, "sets": 4}],
            },
        )
    )
    client.post(f"/actions/{second['id']}/confirm")

    db.expire_all()
    session = db.query(TrainingSession).filter_by(date=date(2026, 3, 15)).one()
    assert [(e.exercise.name, e.weight, e.sets) for e in session.entries] == [
        ("Test Press", 65.0, 3),
        ("Test Raise", 11.0, 4),
    ]


def test_unknown_exercise_makes_the_model_retry_with_suggestions(client: TestClient) -> None:
    events = run(
        client,
        "propose_training_log",
        {"entries": [{"exercise": "Test Pres", "weight": 65}]},  # typo
        {"entries": [{"exercise": "Test Press", "weight": 65}]},
    )

    assert any("Unknown exercise 'Test Pres'" in f and "Test Press" in f for f in feedback)
    payload = proposal(events)["payload"]
    assert isinstance(payload, dict) and payload["entries"][0]["exercise"] == "Test Press"


def test_gear_setting_change_needs_confirmation(client: TestClient, db: Session) -> None:
    action = proposal(run(client, "propose_gear_setting", {"exercise": "TP", "setting": "Stufe 4"}))

    assert action["payload"] == {
        "exercise_id": action["payload"]["exercise_id"],  # type: ignore[index]
        "exercise": "Test Press",
        "old_setting": "Stufe 3",
        "new_setting": "Stufe 4",
    }
    assert db.query(Exercise).filter_by(name="Test Press").one().gear_setting == "Stufe 3"

    client.post(f"/actions/{action['id']}/confirm")
    db.expire_all()
    assert db.query(Exercise).filter_by(name="Test Press").one().gear_setting == "Stufe 4"


def test_briefing_tool_returns_the_overview(client: TestClient) -> None:
    run(client, "training_briefing", {"focus": "Pushday"})

    assert any("Plan Pushday" in f and "Test Press: 62.5 kg × 3" in f for f in feedback)


def test_model_knows_todays_date(client: TestClient) -> None:
    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        seen.append(str(info.instructions))
        yield "ok"

    with get_agent().override(model=FunctionModel(stream_function=stream)):
        client.post("/chat", json={"message": "hi"})

    assert "Today is" in seen[0]
