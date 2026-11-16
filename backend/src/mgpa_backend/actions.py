"""Human-in-the-loop write actions.

The assistant never writes data directly. Its write tools only *propose* an action (a row in
`actions` with status `proposed`); the UI shows it as a card with confirm/discard, and on confirm
the backend executes it here — deterministically, without another LLM call.

Adding a new kind of action = one payload model + one executor in REGISTRY.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.models import (
    Action,
    ActionStatus,
    Exercise,
    Note,
    TrainingEntry,
    TrainingSession,
)


class ActionConflictError(Exception):
    """The action was already confirmed or rejected."""


# --- Payloads (validated again on confirm, so a stored proposal can't bypass the rules) --------


class NoteProposal(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    is_pinned: bool = False


class TrainingEntryProposal(BaseModel):
    exercise_id: int
    exercise: str  # name at proposal time, for the card
    unit: str = "kg"
    weight: float = Field(ge=0, le=1_000)
    sets: int = Field(ge=1, le=20)


class TrainingLogProposal(BaseModel):
    date: date
    focus: str
    entries: list[TrainingEntryProposal] = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=2_000)


class GearSettingProposal(BaseModel):
    exercise_id: int
    exercise: str
    old_setting: str | None
    new_setting: str | None = Field(max_length=500)  # None = remove the setting


# --- Executors: (db, payload) -> (id of the created row, human-readable result) ----------------


def _create_note(db: Session, payload: NoteProposal) -> tuple[int, str]:
    note = Note(title=payload.title, content=payload.content, is_pinned=payload.is_pinned)
    db.add(note)
    db.flush()  # assigns note.id inside the current transaction
    pinned = " and pinned" if payload.is_pinned else ""
    return note.id, f"Note “{payload.title}” saved{pinned}"


def _log_training(db: Session, payload: TrainingLogProposal) -> tuple[int, str]:
    """Add the entries to the session of that day and focus (created if needed), so a later
    "and Skull 35" for the same workout extends it instead of creating a second session."""
    session = db.scalars(
        select(TrainingSession).where(
            TrainingSession.date == payload.date, TrainingSession.focus == payload.focus
        )
    ).first()
    if session is None:
        session = TrainingSession(date=payload.date, focus=payload.focus, notes=payload.notes)
        db.add(session)
    elif payload.notes:
        session.notes = f"{session.notes}\n{payload.notes}" if session.notes else payload.notes
    start = len(session.entries)
    for offset, entry in enumerate(payload.entries):
        db.get_one(Exercise, entry.exercise_id)  # still exists?
        session.entries.append(
            TrainingEntry(
                exercise_id=entry.exercise_id,
                position=start + offset,
                weight=entry.weight,
                sets=entry.sets,
            )
        )
    db.flush()
    return session.id, (
        f"Training {payload.focus} on {payload.date:%d.%m.%Y} saved "
        f"({len(payload.entries)} exercises)"
    )


def _update_gear_setting(db: Session, payload: GearSettingProposal) -> tuple[int, str]:
    exercise = db.get_one(Exercise, payload.exercise_id)
    exercise.gear_setting = payload.new_setting
    db.flush()
    return exercise.id, f"Setting for {exercise.name}: {payload.new_setting or 'removed'}"


@dataclass(frozen=True)
class ActionType:
    payload_model: type[BaseModel]
    label: Callable[[Any], str]
    execute: Callable[[Session, Any], tuple[int, str]]


REGISTRY: dict[str, ActionType] = {
    "create_note": ActionType(
        payload_model=NoteProposal,
        label=lambda p: f"Save note “{p.title}”" + (" (pinned)" if p.is_pinned else ""),
        execute=_create_note,
    ),
    "log_training": ActionType(
        payload_model=TrainingLogProposal,
        label=lambda p: f"Log training {p.focus} · {p.date:%d.%m.%Y} ({len(p.entries)} exercises)",
        execute=_log_training,
    ),
    "update_gear_setting": ActionType(
        payload_model=GearSettingProposal,
        label=lambda p: f"Change setting for {p.exercise}",
        execute=_update_gear_setting,
    ),
}


def propose(db: Session, conversation_id: int, kind: str, payload: BaseModel) -> Action:
    """Store a proposal. Called by the agent's write tools."""
    action_type = REGISTRY[kind]
    action = Action(
        conversation_id=conversation_id,
        kind=kind,
        payload=payload.model_dump(mode="json"),
        label=action_type.label(payload)[:300],
    )
    db.add(action)
    db.commit()
    return action


def confirm(db: Session, action: Action) -> Action:
    """Execute a proposed action and record the result — all in one transaction."""
    if action.status != ActionStatus.PROPOSED:
        raise ActionConflictError(f"Action is already {action.status.value}")
    action_type = REGISTRY[action.kind]
    payload = action_type.payload_model.model_validate(action.payload)
    result_id, summary = action_type.execute(db, payload)
    action.status = ActionStatus.CONFIRMED
    action.result_id = result_id
    action.result_summary = summary
    action.decided_at = datetime.now(UTC)
    db.commit()
    return action


def reject(db: Session, action: Action) -> Action:
    if action.status != ActionStatus.PROPOSED:
        raise ActionConflictError(f"Action is already {action.status.value}")
    action.status = ActionStatus.REJECTED
    action.decided_at = datetime.now(UTC)
    db.commit()
    return action
