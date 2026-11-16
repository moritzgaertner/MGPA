"""Confirm or discard actions the assistant proposed (human-in-the-loop)."""

from fastapi import APIRouter, HTTPException, status

from mgpa_backend import actions
from mgpa_backend.db import DbSession
from mgpa_backend.models import Action
from mgpa_backend.schemas import ActionRead

router = APIRouter(prefix="/actions", tags=["actions"])


def _get_or_404(db: DbSession, action_id: int) -> Action:
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    return action


@router.post("/{action_id}/confirm")
def confirm_action(action_id: int, db: DbSession) -> ActionRead:
    """Execute the proposal (e.g. actually save the note)."""
    try:
        return ActionRead.model_validate(actions.confirm(db, _get_or_404(db, action_id)))
    except actions.ActionConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.post("/{action_id}/reject")
def reject_action(action_id: int, db: DbSession) -> ActionRead:
    """Discard the proposal; nothing is written."""
    try:
        return ActionRead.model_validate(actions.reject(db, _get_or_404(db, action_id)))
    except actions.ActionConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
