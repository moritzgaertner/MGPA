"""CRUD endpoints for notes. Pinned notes are included in every chat turn's system prompt."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from mgpa_backend.db import DbSession
from mgpa_backend.models import Note
from mgpa_backend.schemas import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])


def _get_or_404(db: DbSession, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.post("", status_code=status.HTTP_201_CREATED)
def create_note(body: NoteCreate, db: DbSession) -> NoteRead:
    note = Note(**body.model_dump())
    db.add(note)
    db.commit()
    return NoteRead.model_validate(note)


@router.get("")
def list_notes(db: DbSession, pinned: bool | None = None) -> list[NoteRead]:
    """All notes, pinned first, then most recently changed. `?pinned=true` filters."""
    stmt = select(Note).order_by(Note.is_pinned.desc(), Note.updated_at.desc(), Note.id.desc())
    if pinned is not None:
        stmt = stmt.where(Note.is_pinned == pinned)
    return [NoteRead.model_validate(n) for n in db.scalars(stmt)]


@router.get("/{note_id}")
def get_note(note_id: int, db: DbSession) -> NoteRead:
    return NoteRead.model_validate(_get_or_404(db, note_id))


@router.patch("/{note_id}")
def update_note(note_id: int, body: NoteUpdate, db: DbSession) -> NoteRead:
    """Change title, content and/or pin state — e.g. {"is_pinned": true} to pin."""
    note = _get_or_404(db, note_id)
    for field, value in body.changes().items():
        setattr(note, field, value)
    db.commit()
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: DbSession) -> None:
    db.delete(_get_or_404(db, note_id))
    db.commit()
