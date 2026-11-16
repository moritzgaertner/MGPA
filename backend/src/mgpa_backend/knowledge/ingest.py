"""Ingest one document: read it, chunk it, embed the chunks, store them. Called by Dagster."""

import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mgpa_backend.config import get_settings
from mgpa_backend.knowledge.chunking import ChunkDraft, chunk_text
from mgpa_backend.knowledge.embeddings import Embedder
from mgpa_backend.models import Chunk, Document, DocumentStatus

logger = logging.getLogger(__name__)


def document_path(document: Document) -> Path:
    return get_settings().documents_dir / document.storage_path


def embedding_input(document: Document, draft: ChunkDraft) -> str:
    """Text that is embedded: the chunk prefixed with where it comes from. The header gives
    the vector context ("which document, which section") that the chunk alone may lack."""
    header = (
        document.filename if draft.heading is None else f"{document.filename} › {draft.heading}"
    )
    return f"{header}\n\n{draft.content}"


def pending_document_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(Document.id)
            .where(Document.status == DocumentStatus.PENDING)
            .order_by(Document.id)
        )
    )


def ingest_document(db: Session, document_id: int, embedder: Embedder) -> int:
    """Replace the document's chunks with freshly computed ones. Returns the chunk count.

    Status goes pending → processing → ready, or → failed with the error message (re-raised so
    Dagster marks the run as failed too).
    """
    document = db.get_one(Document, document_id)
    document.status = DocumentStatus.PROCESSING
    document.error = None
    db.commit()

    try:
        text = document_path(document).read_text(encoding="utf-8")
        drafts = chunk_text(text, markdown=document.media_type == "text/markdown")
        if not drafts:
            raise ValueError("The document contains no text.")
        vectors = embedder.embed_documents([embedding_input(document, d) for d in drafts])

        db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        db.add_all(
            Chunk(
                document_id=document_id,
                chunk_index=draft.index,
                heading=draft.heading,
                content=draft.content,
                embedding=vector,
            )
            for draft, vector in zip(drafts, vectors, strict=True)
        )
        document.status = DocumentStatus.READY
        document.chunk_count = len(drafts)
        db.commit()
    except Exception as error:
        db.rollback()
        failed = db.get_one(Document, document_id)
        failed.status = DocumentStatus.FAILED
        failed.error = str(error)[:1_000] or type(error).__name__
        db.commit()
        logger.exception("Ingesting document %s failed", document_id)
        raise

    logger.info("Ingested document %s: %s chunks", document_id, len(drafts))
    return len(drafts)
