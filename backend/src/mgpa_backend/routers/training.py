"""Training data for the /training page: plan with last values, sessions, progress, settings.

Writes from the chat go through proposals (actions.py). Here the user edits directly in the UI
(settings, deleting a wrong session), which needs no extra confirmation.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from mgpa_backend.db import DbSession
from mgpa_backend.models import Exercise, TrainingEntry, TrainingSession
from mgpa_backend.training.service import last_values

router = APIRouter(prefix="/training", tags=["training"])


class LastValueRead(BaseModel):
    date: date
    weight: float
    sets: int


class ExercisePlanRead(BaseModel):
    id: int
    name: str
    muscle: str | None
    kind: str | None
    unit: str
    default_sets: int
    settings: dict[str, str]
    caution: str | None
    aliases: list[str]
    last: LastValueRead | None
    # Has a value, but was not part of the latest session of its focus.
    skipped_last_time: bool


class FocusPlanRead(BaseModel):
    focus: str
    last_session_date: date | None
    exercises: list[ExercisePlanRead]


class EntryRead(BaseModel):
    exercise_id: int
    exercise: str
    unit: str
    weight: float
    sets: int


class SessionRead(BaseModel):
    id: int
    date: date
    focus: str
    notes: str | None
    entries: list[EntryRead]


class HistoryPoint(BaseModel):
    date: date
    weight: float
    sets: int


class MonthCount(BaseModel):
    month: str  # "2026-03"
    sessions: int


class ExerciseUpdate(BaseModel):
    """Direct edit from the UI; only the fields that are sent change."""

    # The complete new set of machine settings, e.g. {"Sitz": "4", "Knie": "3"}.
    settings: dict[str, str] | None = Field(default=None, max_length=20)
    caution: str | None = Field(default=None, max_length=500)


@router.get("/plan")
def get_plan(db: DbSession) -> list[FocusPlanRead]:
    """Active exercises per focus in plan order, with the last weight × sets of each."""
    last = last_values(db)
    exercises = db.scalars(
        select(Exercise).where(Exercise.is_active).order_by(Exercise.focus, Exercise.position)
    ).all()
    plans: list[FocusPlanRead] = []
    for focus in dict.fromkeys(e.focus for e in exercises):
        latest = db.scalars(
            select(TrainingSession)
            .where(TrainingSession.focus == focus)
            .options(selectinload(TrainingSession.entries))
            .order_by(TrainingSession.date.desc(), TrainingSession.id.desc())
            .limit(1)
        ).first()
        done = {entry.exercise_id for entry in latest.entries} if latest else set()
        items = []
        for exercise in (e for e in exercises if e.focus == focus):
            value = last.get(exercise.id)
            items.append(
                ExercisePlanRead(
                    id=exercise.id,
                    name=exercise.name,
                    muscle=exercise.muscle,
                    kind=exercise.kind,
                    unit=exercise.unit,
                    default_sets=exercise.default_sets,
                    settings=exercise.settings,
                    caution=exercise.caution,
                    aliases=exercise.aliases,
                    last=LastValueRead(date=value.date, weight=value.weight, sets=value.sets)
                    if value
                    else None,
                    skipped_last_time=value is not None and exercise.id not in done,
                )
            )
        plans.append(
            FocusPlanRead(
                focus=focus, last_session_date=latest.date if latest else None, exercises=items
            )
        )
    return plans


@router.get("/sessions")
def list_sessions(
    db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 30
) -> list[SessionRead]:
    sessions = db.scalars(
        select(TrainingSession)
        .options(selectinload(TrainingSession.entries).selectinload(TrainingEntry.exercise))
        .order_by(TrainingSession.date.desc(), TrainingSession.id.desc())
        .limit(limit)
    ).all()
    return [
        SessionRead(
            id=s.id,
            date=s.date,
            focus=s.focus,
            notes=s.notes,
            entries=[
                EntryRead(
                    exercise_id=e.exercise_id,
                    exercise=e.exercise.name,
                    unit=e.exercise.unit,
                    weight=e.weight,
                    sets=e.sets,
                )
                for e in s.entries
            ],
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession) -> None:
    session = db.get(TrainingSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    db.delete(session)
    db.commit()


@router.get("/exercises/{exercise_id}/history")
def get_history(exercise_id: int, db: DbSession) -> list[HistoryPoint]:
    """All entries of one exercise, oldest first (for a progress chart)."""
    if db.get(Exercise, exercise_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    rows = db.execute(
        select(TrainingSession.date, TrainingEntry.weight, TrainingEntry.sets)
        .join(TrainingSession)
        .where(TrainingEntry.exercise_id == exercise_id)
        .order_by(TrainingSession.date, TrainingEntry.id)
    ).all()
    return [HistoryPoint(date=d, weight=float(w), sets=s) for d, w, s in rows]


@router.patch("/exercises/{exercise_id}")
def update_exercise(exercise_id: int, body: ExerciseUpdate, db: DbSession) -> ExerciseUpdate:
    exercise = db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    changes = body.model_dump(exclude_unset=True)
    if "settings" in changes:
        exercise.settings = {
            name.strip(): str(value).strip()[:100]
            for name, value in (changes["settings"] or {}).items()
            if name.strip() and str(value).strip()
        }
    if "caution" in changes:
        exercise.caution = (changes["caution"] or "").strip() or None
    db.commit()
    return ExerciseUpdate(settings=exercise.settings, caution=exercise.caution)


@router.get("/stats/monthly")
def sessions_per_month(db: DbSession) -> list[MonthCount]:
    """Number of sessions per month — counted in SQL, not in the browser."""
    month = func.to_char(TrainingSession.date, "YYYY-MM")
    rows = db.execute(
        select(month.label("month"), func.count(TrainingSession.id)).group_by(month).order_by(month)
    ).all()
    return [MonthCount(month=m, sessions=c) for m, c in rows]
