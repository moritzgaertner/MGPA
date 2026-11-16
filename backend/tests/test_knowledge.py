"""Documents API, ingestion and search — with a fake embedder and a temporary documents dir."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mgpa_backend.config import get_settings
from mgpa_backend.knowledge.ingest import ingest_document, pending_documents
from mgpa_backend.knowledge.search import search_chunks
from mgpa_backend.models import Chunk, Document, DocumentStatus
from tests.fakes import FailingEmbedder, FakeEmbedder

PLAN = (
    b"# Plan\n\n## Day A\n\nChest press and butterfly.\n\n## Day B\n\nLeg press and calf raises.\n"
)


@pytest.fixture(autouse=True)
def documents_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Uploaded files go to a temporary folder, never to the real data/ directory."""
    monkeypatch.setattr(get_settings(), "documents_dir", tmp_path)
    yield tmp_path


def upload(client: TestClient, name: str, data: bytes) -> dict[str, object]:
    response = client.post("/documents", files={"file": (name, data, "text/markdown")})
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


# --- API ---------------------------------------------------------------------------------------


def test_upload_stores_file_under_its_fingerprint(client: TestClient, documents_dir: Path) -> None:
    document = upload(client, "plan.md", PLAN)

    assert document["status"] == "pending"
    assert document["filename"] == "plan.md"
    assert document["media_type"] == "text/markdown"
    assert "storage_path" not in document and "sha256" not in document  # internal fields
    stored = list(documents_dir.iterdir())
    assert len(stored) == 1 and stored[0].read_bytes() == PLAN
    assert stored[0].name != "plan.md"


def test_upload_ignores_directories_in_the_filename(client: TestClient) -> None:
    document = upload(client, "../../etc/evil.md", b"hello")

    assert document["filename"] == "evil.md"


@pytest.mark.parametrize(
    ("name", "data", "expected_status"),
    [
        ("cv.pdf", b"%PDF-1.7", 415),  # no PDF by design
        ("notes.md", b"\xff\xfe\x00binary", 422),  # not UTF-8
        ("empty.md", b"   \n", 422),
        ("big.txt", b"x" * 1_000_001, 413),
    ],
)
def test_upload_rejects_unsupported_input(
    client: TestClient, name: str, data: bytes, expected_status: int
) -> None:
    response = client.post("/documents", files={"file": (name, data, "application/octet-stream")})

    assert response.status_code == expected_status


def test_same_content_cannot_be_uploaded_twice(client: TestClient) -> None:
    upload(client, "plan.md", PLAN)

    response = client.post("/documents", files={"file": ("copy.md", PLAN, "text/markdown")})

    assert response.status_code == 409
    assert "plan.md" in response.json()["detail"]


def test_pasted_text_becomes_a_markdown_document(client: TestClient, documents_dir: Path) -> None:
    response = client.post("/documents/text", json={"title": "My CV / 2026", "content": "Skills"})

    assert response.status_code == 201
    assert response.json()["filename"] == "My CV  2026.md"
    assert response.json()["media_type"] == "text/markdown"


def test_delete_removes_row_chunks_and_file(
    client: TestClient, db: Session, documents_dir: Path
) -> None:
    document_id = int(str(upload(client, "plan.md", PLAN)["id"]))
    ingest_document(db, document_id, FakeEmbedder())

    assert client.delete(f"/documents/{document_id}").status_code == 204

    assert db.get(Document, document_id) is None
    assert db.query(Chunk).filter_by(document_id=document_id).count() == 0
    assert list(documents_dir.iterdir()) == []


# --- Ingestion and search ----------------------------------------------------------------------


def test_ingest_chunks_embeds_and_marks_ready(client: TestClient, db: Session) -> None:
    document_id = int(str(upload(client, "plan.md", PLAN)["id"]))
    embedder = FakeEmbedder()

    assert document_id in [i for i, _ in pending_documents(db)]
    count = ingest_document(db, document_id, embedder)

    document = db.get_one(Document, document_id)
    assert document.status == DocumentStatus.READY and document.chunk_count == count == 2
    assert [c.heading for c in document.chunks] == ["Plan › Day A", "Plan › Day B"]
    # The embedded text carries its source as context.
    assert embedder.document_calls[0][1].startswith("plan.md › Plan › Day B")
    assert document_id not in [i for i, _ in pending_documents(db)]


def test_failed_ingestion_is_recorded(client: TestClient, db: Session) -> None:
    document_id = int(str(upload(client, "plan.md", PLAN)["id"]))

    with pytest.raises(RuntimeError):
        ingest_document(db, document_id, FailingEmbedder())

    document = db.get_one(Document, document_id)
    assert document.status == DocumentStatus.FAILED
    assert document.error == "simulated Voyage outage"

    # Re-processing queues it again.
    response = client.post(f"/documents/{document_id}/reprocess")
    assert response.json()["status"] == "pending" and response.json()["error"] is None


def test_search_finds_the_matching_section(client: TestClient, db: Session) -> None:
    document_id = int(str(upload(client, "plan.md", PLAN)["id"]))
    embedder = FakeEmbedder()
    ingest_document(db, document_id, embedder)

    hits = search_chunks(db, embedder.embed_query("leg press calf raises"), limit=5)

    assert hits, "expected at least one hit"
    assert hits[0].source == "plan.md › Plan › Day B"
    assert "Leg press" in hits[0].content


def test_search_ignores_documents_that_are_not_ready(client: TestClient, db: Session) -> None:
    upload(client, "plan.md", PLAN)  # stays pending: never ingested

    assert search_chunks(db, FakeEmbedder().embed_query("leg press")) == []
