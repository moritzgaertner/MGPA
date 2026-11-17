"""Body weight and habits: reading, writing and the text overview the agent gets."""

import difflib
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mgpa_backend.models import BodyWeight, Habit, HabitCheck, HabitSource, TrainingSession
from mgpa_backend.textutil import normalize

# --- Body weight -------------------------------------------------------------------------------


def set_weight(db: Session, day: date, weight: float) -> BodyWeight:
    """Store the weight of a day; an existing value for that day is replaced."""
    entry = db.scalars(select(BodyWeight).where(BodyWeight.date == day)).first()
    if entry is None:
        entry = BodyWeight(date=day, weight=weight)
        db.add(entry)
    else:
        entry.weight = weight
    db.flush()
    return entry


def weight_on(db: Session, day: date) -> float | None:
    return db.scalar(select(BodyWeight.weight).where(BodyWeight.date == day))


def weight_series(db: Session, since: date) -> list[BodyWeight]:
    return list(
        db.scalars(select(BodyWeight).where(BodyWeight.date >= since).order_by(BodyWeight.date))
    )


@dataclass
class WeeklyWeight:
    week_start: date
    average: float
    entries: int


def weekly_averages(db: Session, weeks: int, today: date) -> list[WeeklyWeight]:
    """Average weight per calendar week (Monday–Sunday), computed in SQL, oldest first.

    Single weigh-ins fluctuate by ±1 kg (water, food); the weekly average shows the real trend.
    """
    week = func.date_trunc("week", BodyWeight.date)
    rows = db.execute(
        select(week.label("week"), func.avg(BodyWeight.weight), func.count(BodyWeight.id))
        .where(BodyWeight.date >= week_start(today) - timedelta(weeks=weeks - 1))
        .group_by(week)
        .order_by(week)
    ).all()
    return [WeeklyWeight(w.date(), round(float(avg), 2), n) for w, avg, n in rows]


# --- Habits ------------------------------------------------------------------------------------


def week_start(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def active_habits(db: Session) -> list[Habit]:
    return list(db.scalars(select(Habit).where(Habit.is_active).order_by(Habit.position, Habit.id)))


def done_dates(db: Session, habits: list[Habit], start: date, end: date) -> dict[int, set[date]]:
    """Per habit id: the days in [start, end] on which it was done.

    Manual habits come from habit_checks; "training" habits (Gym) from training sessions.
    """
    result: dict[int, set[date]] = {habit.id: set() for habit in habits}
    checks = db.execute(
        select(HabitCheck.habit_id, HabitCheck.date).where(
            HabitCheck.habit_id.in_(result), HabitCheck.date.between(start, end)
        )
    ).all()
    for habit_id, day in checks:
        result[habit_id].add(day)
    if any(h.source == HabitSource.TRAINING for h in habits):
        trained = set(
            db.scalars(select(TrainingSession.date).where(TrainingSession.date.between(start, end)))
        )
        for habit in habits:
            if habit.source == HabitSource.TRAINING:
                result[habit.id] = trained
    return result


def set_check(db: Session, habit: Habit, day: date, done: bool) -> None:
    """Tick (done=True) or untick a manual habit for a day. Idempotent."""
    if habit.source != HabitSource.MANUAL:
        raise ValueError(f"“{habit.name}” is counted automatically from training sessions.")
    existing = db.scalars(
        select(HabitCheck).where(HabitCheck.habit_id == habit.id, HabitCheck.date == day)
    ).first()
    if done and existing is None:
        db.add(HabitCheck(habit_id=habit.id, date=day))
    elif not done and existing is not None:
        db.delete(existing)
    db.flush()


def resolve_habit(db: Session, name: str) -> Habit | None:
    """Find an active habit by name, ignoring case/accents; a unique prefix also matches
    ("Mails" -> "Mails checken")."""
    wanted = normalize(name)
    habits = active_habits(db)
    exact = [h for h in habits if normalize(h.name) == wanted]
    if exact:
        return exact[0]
    prefix = [h for h in habits if wanted and normalize(h.name).startswith(wanted)]
    return prefix[0] if len(prefix) == 1 else None


def suggest_habits(db: Session, name: str) -> list[str]:
    names = {normalize(h.name): h.name for h in active_habits(db)}
    return [names[n] for n in difflib.get_close_matches(normalize(name), names, n=3, cutoff=0.5)]


# --- Overview for the agent --------------------------------------------------------------------


def _fmt(weight: float) -> str:
    return f"{weight:.1f}".replace(".", ",")


def tracking_overview(db: Session, today: date) -> str:
    """Text for Claude: weight trend and this week's habit progress."""
    lines = ["## Body weight"]
    recent = weight_series(db, today - timedelta(days=13))
    if not recent:
        lines.append("No weigh-ins in the last two weeks.")
    else:
        latest = recent[-1]
        lines.append(f"Latest: {_fmt(latest.weight)} kg on {latest.date:%a %d.%m.}")
        this_week = [w.weight for w in recent if w.date > today - timedelta(days=7)]
        last_week = [w.weight for w in recent if w.date <= today - timedelta(days=7)]
        if this_week:
            avg = sum(this_week) / len(this_week)
            line = f"Average last 7 days: {_fmt(avg)} kg ({len(this_week)} weigh-ins)"
            if last_week:
                prev = sum(last_week) / len(last_week)
                line += f"; the 7 days before: {_fmt(prev)} kg ({avg - prev:+.1f} kg)"
            lines.append(line)

    start = week_start(today)
    habits = active_habits(db)
    lines.append(f"\n## Habits this week (since Monday {start:%d.%m.})")
    if not habits:
        lines.append("No habits defined.")
    done = done_dates(db, habits, start, start + timedelta(days=6))
    for habit in habits:
        days = done[habit.id]
        today_mark = "done today" if today in days else "not yet today"
        auto = " (automatic from training)" if habit.source == HabitSource.TRAINING else ""
        lines.append(
            f"- {habit.name}: {len(days)}/{habit.weekly_goal} this week, {today_mark}{auto}"
        )
    return "\n".join(lines)
