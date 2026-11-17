"""One-off import of the owner's previous habit tracker (habits.json) into Postgres.

The file is read at import time and never committed. Format:
    {"config": {"habits": ["Gym", "Lesen", ...], "goals": {"Lesen": 5, ...}},
     "2026-05-29": {"Lesen": true, "Yoga": false, ...}, ...}
"Gym" becomes an automatic habit counted from training sessions. Re-running is safe.

Usage (from backend/):
    uv run python -m mgpa_backend.tracking.importer <habits.json>
"""

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.models import Habit, HabitSource
from mgpa_backend.tracking.service import set_check

AUTOMATIC = {"gym": HabitSource.TRAINING}


@dataclass
class ImportReport:
    habits_created: int = 0
    habits_updated: int = 0
    checks: int = 0


def import_habits(db: Session, data: dict[str, Any]) -> ImportReport:
    report = ImportReport()
    config = data.get("config", {})
    goals: dict[str, int] = config.get("goals", {})
    habits: dict[str, Habit] = {}
    for position, name in enumerate(config.get("habits", []), start=1):
        habit = db.scalars(select(Habit).where(Habit.name == name)).first()
        if habit is None:
            habit = Habit(name=name, source=AUTOMATIC.get(name.casefold(), HabitSource.MANUAL))
            db.add(habit)
            report.habits_created += 1
        else:
            report.habits_updated += 1
        habit.position = position
        habit.weekly_goal = max(1, min(7, int(goals.get(name, 7))))
        habits[name] = habit
    db.flush()

    for key, day_values in data.items():
        if key == "config" or not isinstance(day_values, dict):
            continue
        day = date.fromisoformat(key)
        for name, done in day_values.items():
            habit = habits.get(name)
            if done is True and habit is not None and habit.source == HabitSource.MANUAL:
                set_check(db, habit, day, done=True)
                report.checks += 1
    db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("habits_json", type=Path)
    args = parser.parse_args()

    from mgpa_backend.db import SessionLocal

    data = json.loads(args.habits_json.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        report = import_habits(db, data)
    print(
        f"Habits: {report.habits_created} created, {report.habits_updated} updated; "
        f"{report.checks} ticks imported."
    )


if __name__ == "__main__":
    main()
