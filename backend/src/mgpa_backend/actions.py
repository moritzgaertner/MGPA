"""Human-in-the-loop write actions.

The assistant never writes data directly. Its write tools only *propose* an action (a row in
`actions` with status `proposed`); the UI shows it as a card with confirm/discard, and on confirm
the backend executes it here — deterministically, without another LLM call.

Adding a new kind of action = one payload model + one executor in REGISTRY.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mgpa_backend.models import Action, ActionStatus, Note


class ActionConflictError(Exception):
    """The action was already confirmed or rejected."""


# --- Payloads (validated again on confirm, so a stored proposal can't bypass the rules) --------


class NoteProposal(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    is_pinned: bool = False


# --- Executors: (db, payload) -> (id of the created row, human-readable result) ----------------


def _create_note(db: Session, payload: NoteProposal) -> tuple[int, str]:
    note = Note(title=payload.title, content=payload.content, is_pinned=payload.is_pinned)
    db.add(note)
    db.flush()  # assigns note.id inside the current transaction
    pinned = " and pinned" if payload.is_pinned else ""
    return note.id, f"Note “{payload.title}” saved{pinned}"


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
