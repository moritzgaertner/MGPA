"""API tests for /notes."""

from fastapi.testclient import TestClient


def create(client: TestClient, **fields: object) -> dict[str, object]:
    body = {"title": "Training plan", "content": "Mon: run 5k", **fields}
    response = client.post("/notes", json=body)
    assert response.status_code == 201
    result: dict[str, object] = response.json()
    return result


def test_create_note_is_unpinned_by_default(client: TestClient) -> None:
    note = create(client)

    assert note["is_pinned"] is False
    assert note["title"] == "Training plan"


def test_pin_and_unpin_note(client: TestClient) -> None:
    note = create(client)

    pinned = client.patch(f"/notes/{note['id']}", json={"is_pinned": True}).json()
    assert pinned["is_pinned"] is True
    assert pinned["content"] == "Mon: run 5k"  # untouched fields stay as they were

    unpinned = client.patch(f"/notes/{note['id']}", json={"is_pinned": False}).json()
    assert unpinned["is_pinned"] is False


def test_update_rejects_null_and_empty_values(client: TestClient) -> None:
    note = create(client)

    assert client.patch(f"/notes/{note['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/notes/{note['id']}", json={"content": ""}).status_code == 422


def test_create_rejects_too_long_content(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "x", "content": "x" * 10_001})

    assert response.status_code == 422


def test_list_puts_pinned_first_and_filters(client: TestClient) -> None:
    plain = create(client, title="Plain")
    pinned = create(client, title="Pinned", is_pinned=True)

    all_ids = [n["id"] for n in client.get("/notes").json()]
    assert all_ids.index(pinned["id"]) < all_ids.index(plain["id"])

    only_pinned = client.get("/notes", params={"pinned": True}).json()
    assert [n["id"] for n in only_pinned] == [pinned["id"]]


def test_delete_note(client: TestClient) -> None:
    note = create(client)

    assert client.delete(f"/notes/{note['id']}").status_code == 204
    assert client.get(f"/notes/{note['id']}").status_code == 404
