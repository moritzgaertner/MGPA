"""Turn the agent's tool arguments into validated training proposals (no LLM logic here)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.actions import (
    MachineSettingsProposal,
    TrainingEntryProposal,
    TrainingLogProposal,
)
from mgpa_backend.config import get_settings
from mgpa_backend.models import Exercise
from mgpa_backend.training.service import majority_focus, resolve_exercise, suggest_exercises


class UnknownExerciseError(ValueError):
    """An exercise name or abbreviation the plan doesn't know. The message helps the model retry."""


class TrainingEntryInput(BaseModel):
    """One exercise as the model passes it to `propose_training_log`."""

    exercise: str = Field(description="Exercise name or the user's abbreviation, e.g. 'BP'")
    weight: float = Field(description="Weight in kg (minutes for timed exercises like planks)")
    sets: int | None = Field(default=None, description="Only if the user gave it")


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _resolve(db: Session, name: str) -> Exercise:
    exercise = resolve_exercise(db, name)
    if exercise is not None:
        return exercise
    suggestions = suggest_exercises(db, name)
    active = db.scalars(select(Exercise.name).where(Exercise.is_active).order_by(Exercise.name))
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    raise UnknownExerciseError(
        f"Unknown exercise '{name}'.{hint} Known exercises: {', '.join(active)}. "
        "If none fits, ask the user instead of guessing."
    )


def build_training_proposal(
    db: Session, entries: list[TrainingEntryInput], day: date, notes: str | None
) -> TrainingLogProposal:
    resolved = [(_resolve(db, entry.exercise), entry) for entry in entries]
    return TrainingLogProposal(
        date=day,
        focus=majority_focus([exercise for exercise, _ in resolved]),
        entries=[
            TrainingEntryProposal(
                exercise_id=exercise.id,
                exercise=exercise.name,
                unit=exercise.unit,
                weight=entry.weight,
                sets=entry.sets or exercise.default_sets,
            )
            for exercise, entry in resolved
        ],
        notes=notes,
    )


def build_settings_proposal(
    db: Session, exercise_name: str, changes: dict[str, str], replace: bool
) -> MachineSettingsProposal:
    """Merge the changed settings into the current ones (an empty value removes a setting).
    With `replace`, the given settings become the complete new set."""
    exercise = _resolve(db, exercise_name)
    if not changes:
        raise ValueError('No settings given, e.g. {"Sitz": "4"}.')
    new = {} if replace else dict(exercise.settings)
    for name, value in changes.items():
        key, text = name.strip(), str(value).strip()
        if not key:
            continue
        if text:
            new[key] = text[:100]
        else:
            new.pop(key, None)
    return MachineSettingsProposal(
        exercise_id=exercise.id,
        exercise=exercise.name,
        old_settings=dict(exercise.settings),
        new_settings=new,
    )


def parse_day(value: str | None) -> date:
    """ISO date from the model, or today if missing."""
    if not value:
        return today()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid date '{value}', use YYYY-MM-DD.") from error
