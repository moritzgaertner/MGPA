"""API tests for /conversations, run against the rolled-back test session (see conftest.py)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mgpa_backend.models import Conversation, Message, MessageRole


def test_create_conversation_without_title(client: TestClient) -> None:
    response = client.post("/conversations", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] is None
    assert isinstance(body["id"], int)
    assert body["created_at"] and body["updated_at"]


def test_create_conversation_rejects_too_long_title(client: TestClient) -> None:
    response = client.post("/conversations", json={"title": "x" * 201})

    assert response.status_code == 422  # validation error, nothing was saved


def test_list_returns_most_recent_first(client: TestClient) -> None:
    first = client.post("/conversations", json={"title": "first"}).json()
    second = client.post("/conversations", json={"title": "second"}).json()

    response = client.get("/conversations")

    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert ids.index(second["id"]) < ids.index(first["id"])


def test_list_respects_limit(client: TestClient) -> None:
    for i in range(3):
        client.post("/conversations", json={"title": f"c{i}"})

    assert len(client.get("/conversations", params={"limit": 2}).json()) == 2
    assert client.get("/conversations", params={"limit": 0}).status_code == 422


def test_get_conversation_includes_messages_in_order(client: TestClient, db: Session) -> None:
    conversation = Conversation(
        title="with messages",
        messages=[
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi!"),
        ],
    )
    db.add(conversation)
    db.commit()

    response = client.get(f"/conversations/{conversation.id}")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Hello"),
        ("assistant", "Hi!"),
    ]


def test_unknown_conversation_returns_404(client: TestClient) -> None:
    assert client.get("/conversations/999999").status_code == 404
    assert client.patch("/conversations/999999", json={"title": "x"}).status_code == 404
    assert client.delete("/conversations/999999").status_code == 404


def test_rename_conversation(client: TestClient) -> None:
    created = client.post("/conversations", json={}).json()

    response = client.patch(f"/conversations/{created['id']}", json={"title": "Job search"})

    assert response.status_code == 200
    assert response.json()["title"] == "Job search"


def test_rename_rejects_empty_title(client: TestClient) -> None:
    created = client.post("/conversations", json={}).json()

    response = client.patch(f"/conversations/{created['id']}", json={"title": ""})

    assert response.status_code == 422


def test_delete_conversation(client: TestClient) -> None:
    created = client.post("/conversations", json={}).json()

    response = client.delete(f"/conversations/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/conversations/{created['id']}").status_code == 404
