"""Sensor + asset tests with a fake embedder. These commit to the test database and clean up."""

import hashlib
from collections.abc import Iterator, Sequence
from pathlib import Path

import dagster as dg
import pytest
from mgpa_backend.db import SessionLocal
from mgpa_backend.knowledge.embeddings import Embedder
from mgpa_backend.models import EMBEDDING_DIMENSIONS, Document, DocumentStatus

from mgpa_pipelines.definitions import (
    DOCUMENTS,
    EmbedderResource,
    defs,
    document_chunks,
    pending_documents_sensor,
)


class FakeEmbedder:
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


class FakeEmbedderResource(EmbedderResource):
    def get(self) -> Embedder:
        return FakeEmbedder()


@pytest.fixture
def document(documents_dir: Path) -> Iterator[int]:
    """A real (committed) pending document in the test database, removed afterwards."""
    data = b"# Notes\n\n## Topic\n\nSome text to ingest.\n"
    sha = hashlib.sha256(data + str(documents_dir).encode()).hexdigest()  # unique per test
    (documents_dir / f"{sha}.md").write_bytes(data)
    with SessionLocal() as db:
        doc = Document(
            filename="notes.md",
            media_type="text/markdown",
            size_bytes=len(data),
            sha256=sha,
            storage_path=f"{sha}.md",
        )
        db.add(doc)
        db.commit()
        document_id = doc.id
    yield document_id
    with SessionLocal() as db:
        leftover = db.get(Document, document_id)
        if leftover is not None:
            db.delete(leftover)
            db.commit()


def test_definitions_load() -> None:
    assert defs.resolve_job_def("ingest_documents") is not None


def test_sensor_requests_a_run_for_each_pending_document(document: int) -> None:
    instance = dg.DagsterInstance.ephemeral()
    context = dg.build_sensor_context(instance=instance)

    result = pending_documents_sensor(context)

    assert isinstance(result, dg.SensorResult)
    assert str(document) in [r.partition_key for r in result.run_requests or []]
    added = [
        key
        for request in result.dynamic_partitions_requests or []
        for key in request.partition_keys
    ]
    assert str(document) in added


def test_asset_ingests_the_document(document: int) -> None:
    instance = dg.DagsterInstance.ephemeral()
    instance.add_dynamic_partitions(DOCUMENTS, [str(document)])

    result = dg.materialize(
        [document_chunks],
        partition_key=str(document),
        instance=instance,
        resources={"embedder": FakeEmbedderResource()},
    )

    assert result.success
    with SessionLocal() as db:
        ingested = db.get_one(Document, document)
        assert ingested.status == DocumentStatus.READY
        assert ingested.chunk_count == 1
        assert ingested.chunks[0].heading == "Notes › Topic"
