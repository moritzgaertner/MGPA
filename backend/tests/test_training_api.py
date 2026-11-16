"""REST endpoints of the /training page (synthetic plan)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mgpa_backend.training.importer import import_training, parse_context
from tests.test_training import CONTEXT, ROWS


@pytest.fixture(autouse=True)
def plan(db: Session) -> Iterator[None]:
    import_training(db, parse_context(CONTEXT), ROWS)
    yield


def test_plan_lists_focuses_with_last_values(client: TestClient) -> None:
    plans = {p["focus"]: p for p in client.get("/training/plan").json()}

    push = plans["Pushday"]
    assert push["last_session_date"] == "2026-03-08"
    press, raise_ = push["exercises"][:2]
    assert (press["name"], press["last"]["weight"], press["skipped_last_time"]) == (
        "Test Press",
        62.5,
        False,
    )
    assert (raise_["name"], raise_["skipped_last_time"]) == ("Test Raise", True)
    assert all(e["name"] != "Old Fly" for p in plans.values() for e in p["exercises"])


def test_sessions_newest_first_and_delete(client: TestClient) -> None:
    sessions = client.get("/training/sessions").json()
    assert [s["date"] for s in sessions][:3] == ["2026-03-08", "2026-03-04", "2026-03-01"]
    assert sessions[0]["entries"] == [
        {
            "exercise_id": sessions[0]["entries"][0]["exercise_id"],
            "exercise": "Test Press",
            "unit": "kg",
            "weight": 62.5,
            "sets": 3,
        }
    ]

    assert client.delete(f"/training/sessions/{sessions[0]['id']}").status_code == 204
    assert client.get("/training/sessions").json()[0]["date"] == "2026-03-04"


def test_history_oldest_first(client: TestClient) -> None:
    press = client.get("/training/plan").json()
    press_id = next(e["id"] for p in press for e in p["exercises"] if e["name"] == "Test Press")

    history = client.get(f"/training/exercises/{press_id}/history").json()

    assert [(h["date"], h["weight"]) for h in history] == [
        ("2026-03-01", 60.0),
        ("2026-03-08", 62.5),
    ]


def test_edit_gear_setting_directly(client: TestClient) -> None:
    plan = client.get("/training/plan").json()
    press_id = next(e["id"] for p in plan for e in p["exercises"] if e["name"] == "Test Press")

    updated = client.patch(
        f"/training/exercises/{press_id}", json={"gear_setting": " Stufe 5 "}
    ).json()

    assert updated["gear_setting"] == "Stufe 5"


def test_monthly_counts(client: TestClient) -> None:
    months = {m["month"]: m["sessions"] for m in client.get("/training/stats/monthly").json()}

    assert months["2026-03"] >= 3
