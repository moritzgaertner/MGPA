"""Knowledge-base documents: upload (file or pasted text), list, delete, re-process.

The API only stores the file and a `pending` row; the Dagster pipeline does the ingestion.
"""

import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from mgpa_backend.config import get_settings
from mgpa_backend.db import DbSession
from mgpa_backend.models import Document, DocumentStatus
from mgpa_backend.schemas import DocumentRead, DocumentTextCreate

router = APIRouter(prefix="/documents", tags=["documents"])

# No PDF by design: Markdown and plain text only (convert PDFs outside MGPA if needed).
ALLOWED_TYPES = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain"}
MAX_BYTES = 1_000_000


def _store_document(db: DbSession, filename: str, data: bytes) -> Document:
    suffix = Path(filename).suffix.lower()
    media_type = ALLOWED_TYPES.get(suffix)
    if media_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only .md, .markdown and .txt files are supported",
        )
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is larger than 1 MB")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "File is not UTF-8 text"
        ) from error
    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File is empty")

    sha256 = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Document).where(Document.sha256 == sha256))
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"This content was already uploaded as “{existing.filename}”"
        )

    # Stored under its fingerprint, never under the client-supplied name: no path tricks
    # ("../../etc/passwd") and no collisions between equally named files.
    storage_path = f"{sha256}{suffix}"
    documents_dir = get_settings().documents_dir
    documents_dir.mkdir(parents=True, exist_ok=True)
    (documents_dir / storage_path).write_bytes(data)

    document = Document(
        filename=Path(filename).name[:255],  # display name only, without any directories
        media_type=media_type,
        size_bytes=len(data),
        sha256=sha256,
        storage_path=storage_path,
    )
    db.add(document)
    db.commit()
    return document


def _get_or_404(db: DbSession, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_document(file: UploadFile, db: DbSession) -> DocumentRead:
    """Upload a Markdown or text file. It is ingested in the background (status → ready)."""
    data = file.file.read(MAX_BYTES + 1)
    return DocumentRead.model_validate(_store_document(db, file.filename or "upload.txt", data))


@router.post("/text", status_code=status.HTTP_201_CREATED)
def create_text_document(body: DocumentTextCreate, db: DbSession) -> DocumentRead:
    """Store pasted text as a Markdown document named after its title."""
    stem = re.sub(r"[^\w\- ]+", "", body.title).strip() or "pasted-text"
    data = body.content.encode("utf-8")
    return DocumentRead.model_validate(_store_document(db, f"{stem}.md", data))


@router.get("")
def list_documents(db: DbSession) -> list[DocumentRead]:
    documents = db.scalars(
        select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    )
    return [DocumentRead.model_validate(d) for d in documents]


@router.post("/{document_id}/reprocess")
def reprocess_document(document_id: int, db: DbSession) -> DocumentRead:
    """Queue a document for ingestion again (e.g. after a failure)."""
    document = _get_or_404(db, document_id)
    document.status = DocumentStatus.PENDING
    document.error = None
    db.commit()
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: DbSession) -> None:
    """Delete the document, its chunks (ON DELETE CASCADE) and the stored file."""
    document = _get_or_404(db, document_id)
    path = get_settings().documents_dir / document.storage_path
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
