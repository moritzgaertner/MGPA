"""Body weight and habits: service, REST endpoints, importer and chat proposals."""

import json
from collections.abc import AsyncIterator, Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy.orm import Session

from mgpa_backend.agent import get_agent
from mgpa_backend.models import BodyWeight, HabitCheck, TrainingSession
from mgpa_backend.tracking import service
from mgpa_backend.tracking.importer import import_habits
from mgpa_backend.training.tools import today
from tests.test_chat_api import parse_sse
from tests.test_training_tools import feedback, proposal, run

HABITS_JSON = {
    "config": {
        "habits": ["Gym", "Lesen", "Mails checken", "Yoga"],
        "goals": {"Gym": 3, "Lesen": 5, "Mails checken": 5, "Yoga": 3},
    },
    "2026-05-29": {"Lesen": False, "Mails checken": True, "Yoga": True},
    "2026-05-30": {"Lesen": True, "Mails checken": False, "Yoga": False},
}


@pytest.fixture(autouse=True)
def habits(db: Session) -> Iterator[None]:
    import_habits(db, HABITS_JSON)
    feedback.clear()
    yield


def habit_id(client: TestClient, name: str) -> int:
    habits = client.get("/tracking/habits").json()["habits"]
    return int(next(h["id"] for h in habits if h["name"] == name))


# --- Importer ----------------------------------------------------------------------------------


def test_import_creates_habits_with_goals_and_ticks(client: TestClient, db: Session) -> None:
    week = client.get("/tracking/habits", params={"week": "2026-05-29"}).json()

    assert week["week_start"] == "2026-05-25"  # Monday
    habits = {h["name"]: h for h in week["habits"]}
    assert list(habits) == ["Gym", "Lesen", "Mails checken", "Yoga"]  # import order
    assert (habits["Gym"]["source"], habits["Gym"]["weekly_goal"]) == ("training", 3)
    assert habits["Lesen"]["done"] == ["2026-05-30"]
    assert habits["Yoga"]["done"] == ["2026-05-29"]

    # Re-running changes nothing.
    report = import_habits(db, HABITS_JSON)
    assert (report.habits_created, report.habits_updated) == (0, 4)
    assert db.query(HabitCheck).count() == 3


# --- Habits API --------------------------------------------------------------------------------


def test_gym_is_derived_from_training_sessions(client: TestClient, db: Session) -> None:
    db.add(TrainingSession(date=date(2026, 5, 26), focus="Brust"))
    db.flush()

    week = client.get("/tracking/habits", params={"week": "2026-05-26"}).json()
    gym = next(h for h in week["habits"] if h["name"] == "Gym")
    assert gym["done"] == ["2026-05-26"]

    # Gym can't be ticked by hand.
    response = client.put(f"/tracking/habits/{gym['id']}/checks/2026-05-27")
    assert response.status_code == 409


def test_tick_and_untick_are_idempotent(client: TestClient) -> None:
    yoga = habit_id(client, "Yoga")
    for _ in range(2):
        assert client.put(f"/tracking/habits/{yoga}/checks/2026-06-02").status_code == 204

    def done() -> list[str]:
        week = client.get("/tracking/habits", params={"week": "2026-06-02"}).json()
        return next(h["done"] for h in week["habits"] if h["id"] == yoga)

    assert done() == ["2026-06-02"]
    assert client.delete(f"/tracking/habits/{yoga}/checks/2026-06-02").status_code == 204
    assert client.delete(f"/tracking/habits/{yoga}/checks/2026-06-02").status_code == 204
    assert done() == []


def test_create_update_and_remove_habit(client: TestClient) -> None:
    assert client.post("/tracking/habits", json={"name": "Vitamine"}).status_code == 201
    assert client.post("/tracking/habits", json={"name": "vitamine"}).status_code == 409

    vitamins = habit_id(client, "Vitamine")
    client.patch(f"/tracking/habits/{vitamins}", json={"weekly_goal": 6})
    habits = {h["name"]: h for h in client.get("/tracking/habits").json()["habits"]}
    assert habits["Vitamine"]["weekly_goal"] == 6
    assert list(habits)[-1] == "Vitamine"  # appended at the end

    client.patch(f"/tracking/habits/{vitamins}", json={"is_active": False})
    names = [h["name"] for h in client.get("/tracking/habits").json()["habits"]]
    assert "Vitamine" not in names


# --- Body weight API ---------------------------------------------------------------------------


def test_weight_one_value_per_day_and_weekly_average(client: TestClient, db: Session) -> None:
    monday = service.week_start(today())
    client.put(f"/tracking/weight/{monday}", json={"weight": 83.0})
    client.put(f"/tracking/weight/{monday}", json={"weight": 82.4})  # replaces
    last_week = monday - timedelta(days=3)
    client.put(f"/tracking/weight/{last_week}", json={"weight": 84.0})

    assert db.query(BodyWeight).count() == 2
    points = client.get("/tracking/weight").json()
    assert [p["weight"] for p in points] == [84.0, 82.4]

    weekly = client.get("/tracking/weight/weekly").json()
    assert [(w["week_start"], w["average"]) for w in weekly] == [
        (str(monday - timedelta(weeks=1)), 84.0),
        (str(monday), 82.4),
    ]

    assert client.delete(f"/tracking/weight/{monday}").status_code == 204
    assert client.delete(f"/tracking/weight/{monday}").status_code == 404


def test_implausible_weight_is_rejected(client: TestClient) -> None:
    assert client.put("/tracking/weight/2026-06-01", json={"weight": 824}).status_code == 422


# --- Chat proposals ----------------------------------------------------------------------------


def test_weight_from_chat_needs_confirmation(client: TestClient, db: Session) -> None:
    action = proposal(run(client, "propose_weight", {"weight": 82.4, "date": "2026-06-01"}))

    assert action["label"] == "Log weight 82.4 kg · 01.06.2026"
    assert db.query(BodyWeight).count() == 0  # nothing saved yet

    assert client.post(f"/actions/{action['id']}/confirm").status_code == 200
    db.expire_all()
    assert db.query(BodyWeight).one().weight == 82.4


def test_habit_checkin_resolves_names_and_retries_unknown_ones(
    client: TestClient, db: Session
) -> None:
    events = run(
        client,
        "propose_habit_checkin",
        {"habits": ["lesen", "Joga"], "date": "2026-06-01"},  # typo
        {"habits": ["lesen", "Mails", "Yoga"], "date": "2026-06-01"},  # prefix "Mails"
    )

    assert any("Unknown habit 'Joga'" in f and "Yoga" in f for f in feedback)
    action = proposal(events)
    payload = action["payload"]
    assert isinstance(payload, dict)
    assert [h["name"] for h in payload["habits"]] == ["Lesen", "Mails checken", "Yoga"]

    client.post(f"/actions/{action['id']}/confirm")
    db.expire_all()
    assert db.query(HabitCheck).filter_by(date=date(2026, 6, 1)).count() == 3


def test_parallel_tool_calls_share_the_db_session_safely(client: TestClient) -> None:
    """Regression: Claude called propose_weight and propose_habit_checkin in ONE response; both
    ran concurrently on the same SQLAlchemy session -> "This transaction is closed"."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        if len(messages) > 1:
            yield "Ready to confirm."
            return
        yield {
            0: DeltaToolCall(name="propose_weight", json_args=json.dumps({"weight": 82.4})),
            1: DeltaToolCall(
                name="propose_habit_checkin", json_args=json.dumps({"habits": ["Lesen", "Yoga"]})
            ),
        }

    with get_agent().override(model=FunctionModel(stream_function=stream)):
        events = parse_sse(client.post("/chat", json={"message": "82,4 und Lesen, Yoga"}).text)

    kinds = sorted(data["action"]["kind"] for name, data in events if name == "proposal")
    assert kinds == ["check_habits", "log_weight"]
    assert not [data for name, data in events if name == "error"]


def test_gym_cannot_be_ticked_from_chat(client: TestClient) -> None:
    run(client, "propose_habit_checkin", {"habits": ["Gym"]})

    assert any("counted automatically" in f for f in feedback)


def test_overview_tool_reports_trend_and_progress(client: TestClient) -> None:
    now = today()
    client.put(f"/tracking/weight/{now - timedelta(days=8)}", json={"weight": 84.0})
    client.put(f"/tracking/weight/{now}", json={"weight": 82.5})
    client.put(f"/tracking/habits/{habit_id(client, 'Lesen')}/checks/{now}")

    run(client, "tracking_overview", {})

    text = next(f for f in feedback if "## Body weight" in f)
    assert "Latest: 82,5 kg" in text
    assert "(-1.5 kg)" in text
    assert "- Lesen: 1/5 this week, done today" in text
    assert "- Gym: 0/3 this week, not yet today (automatic from training)" in text
