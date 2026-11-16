"""Training queries and text for the agent: resolve exercise names, last values, briefings."""

import difflib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from mgpa_backend.models import Exercise, TrainingEntry, TrainingSession


def normalize(text: str) -> str:
    """Case-, space- and punctuation-insensitive key: "Rev. Butterfly" == "rev butterfly"."""
    return re.sub(r"[^\w]+", " ", text.casefold()).strip()


def _lookup_table(db: Session) -> dict[str, Exercise]:
    """normalized name/alias -> exercise. Active exercises win over inactive ones."""
    table: dict[str, Exercise] = {}
    exercises = db.scalars(select(Exercise).order_by(Exercise.is_active, Exercise.id)).all()
    for exercise in exercises:  # inactive first, so active ones overwrite on a clash
        for key in [exercise.name, *exercise.aliases]:
            table[normalize(key)] = exercise
    return table


def resolve_exercise(db: Session, text: str) -> Exercise | None:
    """Find an exercise by its exact name or one of its abbreviations (e.g. "BP", "Skull")."""
    return _lookup_table(db).get(normalize(text))


def suggest_exercises(db: Session, text: str, limit: int = 5) -> list[str]:
    """Closest exercise names for an unknown input (for a helpful retry message)."""
    table = _lookup_table(db)
    matches = difflib.get_close_matches(normalize(text), table.keys(), n=limit * 2, cutoff=0.4)
    names = list(dict.fromkeys(table[m].name for m in matches))
    return names[:limit]


def majority_focus(exercises: list[Exercise]) -> str:
    return Counter(e.focus for e in exercises).most_common(1)[0][0]


@dataclass(frozen=True)
class LastValue:
    date: date
    weight: float
    sets: int


def last_values(db: Session) -> dict[int, LastValue]:
    """Most recent weight × sets per exercise (Postgres DISTINCT ON: first row per exercise)."""
    rows = db.execute(
        select(
            TrainingEntry.exercise_id,
            TrainingSession.date,
            TrainingEntry.weight,
            TrainingEntry.sets,
        )
        .join(TrainingSession)
        .ext(distinct_on(TrainingEntry.exercise_id))
        .order_by(TrainingEntry.exercise_id, TrainingSession.date.desc(), TrainingEntry.id.desc())
    ).all()
    return {row[0]: LastValue(row[1], float(row[2]), row[3]) for row in rows}


def format_amount(weight: float, sets: int, unit: str) -> str:
    value = f"{weight:g}"
    return f"{value} {unit} × {sets}"


def focuses(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(Exercise.focus).where(Exercise.is_active).distinct().order_by(Exercise.focus)
        )
    )


def training_overview(db: Session, focus: str) -> str:
    """Briefing for one focus: plan order, machine settings, cautions, last weights — like the
    owner's old Telegram /briefing. Without a focus: last session per focus."""
    known = focuses(db)
    match = next((f for f in known if normalize(f) == normalize(focus)), None)
    if match is None:
        lines = [f"Training focuses: {', '.join(known) or 'none yet'}."]
        for name in known:
            session = db.scalars(
                select(TrainingSession)
                .where(TrainingSession.focus == name)
                .order_by(TrainingSession.date.desc())
                .limit(1)
            ).first()
            lines.append(
                f"- {name}: last session {session.date:%d.%m.%Y}"
                if session
                else f"- {name}: none yet"
            )
        return "\n".join(lines)

    last = last_values(db)
    last_session = db.scalars(
        select(TrainingSession)
        .where(TrainingSession.focus == match)
        .order_by(TrainingSession.date.desc(), TrainingSession.id.desc())
        .limit(1)
    ).first()
    done_last_time = {e.exercise_id for e in last_session.entries} if last_session else set()
    exercises = db.scalars(
        select(Exercise)
        .where(Exercise.focus == match, Exercise.is_active)
        .order_by(Exercise.position, Exercise.name)
    ).all()

    header = f"Plan {match}" + (
        f" — last session {last_session.date:%d.%m.%Y}" if last_session else " — no session yet"
    )
    lines = [header]
    for number, exercise in enumerate(exercises, 1):
        value = last.get(exercise.id)
        amount = format_amount(value.weight, value.sets, exercise.unit) if value else "no value yet"
        details = []
        if value and exercise.id not in done_last_time:
            details.append(f"from {value.date:%d.%m.%Y}, skipped last time")
        if exercise.gear_setting:
            details.append(f"setting: {exercise.gear_setting}")
        if exercise.caution:
            details.append(f"⚠️ {exercise.caution}")
        if exercise.default_sets != 3:
            details.append(f"usually {exercise.default_sets} sets")
        suffix = f" ({'; '.join(details)})" if details else ""
        lines.append(f"{number}. {exercise.name}: {amount}{suffix}")
    return "\n".join(lines)


def exercise_history(db: Session, exercise: Exercise, limit: int = 12) -> str:
    rows = db.execute(
        select(TrainingSession.date, TrainingEntry.weight, TrainingEntry.sets)
        .join(TrainingSession)
        .where(TrainingEntry.exercise_id == exercise.id)
        .order_by(TrainingSession.date.desc())
        .limit(limit)
    ).all()
    if not rows:
        return f"No entries for {exercise.name} yet."
    lines = [f"{exercise.name} — last {len(rows)} entries (newest first):"]
    lines += [f"- {d:%d.%m.%Y}: {format_amount(float(w), s, exercise.unit)}" for d, w, s in rows]
    return "\n".join(lines)
