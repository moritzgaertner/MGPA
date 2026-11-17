"""Body weight and habits for the /tracking page.

Writes from the chat go through proposals (actions.py). Here the user edits directly in the UI
(weigh-in field, habit checkboxes), which needs no extra confirmation.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from mgpa_backend.db import DbSession
from mgpa_backend.models import BodyWeight, Habit, HabitSource
from mgpa_backend.tracking import service
from mgpa_backend.training.tools import today

router = APIRouter(prefix="/tracking", tags=["tracking"])


class WeightPoint(BaseModel):
    date: date
    weight: float


class WeightUpdate(BaseModel):
    weight: float = Field(ge=20, le=400)


class WeeklyWeightRead(BaseModel):
    week_start: date
    average: float
    entries: int


class HabitRead(BaseModel):
    id: int
    name: str
    weekly_goal: int
    source: str
    # Days of the requested week on which the habit was done.
    done: list[date]


class HabitWeekRead(BaseModel):
    week_start: date
    today: date
    habits: list[HabitRead]


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    weekly_goal: int = Field(default=7, ge=1, le=7)


class HabitUpdate(BaseModel):
    """Only the fields that are sent change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    weekly_goal: int | None = Field(default=None, ge=1, le=7)
    is_active: bool | None = None


# --- Body weight -------------------------------------------------------------------------------


@router.get("/weight")
def list_weights(
    db: DbSession, days: Annotated[int, Query(ge=1, le=3650)] = 180
) -> list[WeightPoint]:
    """Weigh-ins of the last `days` days, oldest first (for the chart)."""
    entries = service.weight_series(db, today() - timedelta(days=days - 1))
    return [WeightPoint(date=e.date, weight=e.weight) for e in entries]


@router.get("/weight/weekly")
def weekly_weights(
    db: DbSession, weeks: Annotated[int, Query(ge=1, le=520)] = 12
) -> list[WeeklyWeightRead]:
    return [
        WeeklyWeightRead(week_start=w.week_start, average=w.average, entries=w.entries)
        for w in service.weekly_averages(db, weeks, today())
    ]


@router.put("/weight/{day}")
def put_weight(day: date, body: WeightUpdate, db: DbSession) -> WeightPoint:
    entry = service.set_weight(db, day, body.weight)
    db.commit()
    return WeightPoint(date=entry.date, weight=entry.weight)


@router.delete("/weight/{day}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weight(day: date, db: DbSession) -> None:
    entry = db.scalars(select(BodyWeight).where(BodyWeight.date == day)).first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No weight for this day")
    db.delete(entry)
    db.commit()


# --- Habits ------------------------------------------------------------------------------------


@router.get("/habits")
def habit_week(db: DbSession, week: date | None = None) -> HabitWeekRead:
    """Active habits with the days they were done in the week containing `week` (default: now)."""
    now = today()
    start = service.week_start(week or now)
    habits = service.active_habits(db)
    done = service.done_dates(db, habits, start, start + timedelta(days=6))
    return HabitWeekRead(
        week_start=start,
        today=now,
        habits=[
            HabitRead(
                id=h.id,
                name=h.name,
                weekly_goal=h.weekly_goal,
                source=h.source,
                done=sorted(done[h.id]),
            )
            for h in habits
        ],
    )


def _get_habit(db: DbSession, habit_id: int) -> Habit:
    habit = db.get(Habit, habit_id)
    if habit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Habit not found")
    return habit


def _set_check(db: DbSession, habit_id: int, day: date, done: bool) -> None:
    try:
        service.set_check(db, _get_habit(db, habit_id), day, done)
    except ValueError as error:  # automatic habit (Gym)
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    db.commit()


@router.put("/habits/{habit_id}/checks/{day}", status_code=status.HTTP_204_NO_CONTENT)
def tick_habit(habit_id: int, day: date, db: DbSession) -> None:
    _set_check(db, habit_id, day, done=True)


@router.delete("/habits/{habit_id}/checks/{day}", status_code=status.HTTP_204_NO_CONTENT)
def untick_habit(habit_id: int, day: date, db: DbSession) -> None:
    _set_check(db, habit_id, day, done=False)


@router.post("/habits", status_code=status.HTTP_201_CREATED)
def create_habit(body: HabitCreate, db: DbSession) -> HabitCreate:
    name = body.name.strip()
    existing = db.scalars(select(Habit).where(func.lower(Habit.name) == name.lower())).first()
    if existing is not None and existing.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "A habit with this name exists")
    if existing is not None:  # re-activate a removed habit (keeps its history)
        existing.is_active = True
        existing.weekly_goal = body.weekly_goal
    else:
        position = (db.scalar(select(func.max(Habit.position))) or 0) + 1
        db.add(
            Habit(
                name=name,
                weekly_goal=body.weekly_goal,
                position=position,
                source=HabitSource.MANUAL,
            )
        )
    db.commit()
    return HabitCreate(name=name, weekly_goal=body.weekly_goal)


@router.patch("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_habit(habit_id: int, body: HabitUpdate, db: DbSession) -> None:
    """Rename, change the goal, or remove (is_active=false keeps the history)."""
    habit = _get_habit(db, habit_id)
    for field_name, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(habit, field_name, value.strip() if isinstance(value, str) else value)
    db.commit()
