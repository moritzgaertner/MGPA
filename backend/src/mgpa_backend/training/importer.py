"""One-off import of the owner's previous training tracker (CONTEXT.md + Excel) into Postgres.

Personal data (plan, settings, history) is read from the owner's files at import time and never
committed to the repository. Re-running is safe: exercises are updated, existing sessions skipped.

Usage (from backend/):
    uv run python -m mgpa_backend.training.importer <CONTEXT.md> <Training_Tracker.xlsx>
"""

import argparse
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.models import Exercise, TrainingEntry, TrainingSession

_FOCUS_CODE = re.compile(r"`\d+\s*-\s*([^`]+)`")  # "### TAG A — … (`1 - Brust`)" -> "Brust"
_SETS_HINT = re.compile(r"immer\s+(\d+)")  # "⚠️ immer 2 Arbeitssätze" -> 2


@dataclass
class ExerciseSpec:
    name: str
    focus: str
    position: int
    kind: str | None = None
    muscle: str | None = None
    default_sets: int = 3
    gear_setting: str | None = None
    cautions: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and not re.fullmatch(r"\|[\s\-|:]+\|", stripped)


def _empty(value: str) -> bool:
    return value in ("", "—", "-")


def focus_from_label(label: str) -> str:
    """Excel focus "1 - Brust" -> "Brust"."""
    return re.sub(r"^\s*\d+\s*-\s*", "", label).strip()


def parse_context(markdown: str) -> dict[str, ExerciseSpec]:
    """Exercises (plan tables), machine settings and abbreviations from CONTEXT.md."""
    specs: dict[str, ExerciseSpec] = {}
    section = ""
    focus: str | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            focus = None
            continue
        if line.startswith("### "):
            match = _FOCUS_CODE.search(line)
            focus = focus_from_label(match.group(1)) if match else None
            continue
        if not _is_table_row(line):
            continue
        cells = _cells(line)

        if section.startswith("trainingsplan") and focus and cells[0].isdigit() and len(cells) >= 4:
            spec = ExerciseSpec(
                name=cells[1], focus=focus, position=int(cells[0]), kind=cells[2], muscle=cells[3]
            )
            for extra in cells[4:]:
                if hint := _SETS_HINT.search(extra):
                    spec.default_sets = int(hint.group(1))
                elif not _empty(extra):
                    spec.cautions.append(extra.lstrip("⚠️ ").strip())
            specs[spec.name] = spec
        elif section.startswith("geräteeinstellungen") and len(cells) >= 2 and cells[0] in specs:
            spec = specs[cells[0]]
            spec.gear_setting = None if _empty(cells[1]) else cells[1]
            spec.cautions += [c.lstrip("⚠️ ").strip() for c in cells[2:] if not _empty(c)]
        elif section.startswith("abkürzungsschlüssel") and len(cells) >= 2 and cells[1] in specs:
            spec = specs[cells[1]]
            spec.aliases += [a.strip() for a in cells[0].split("/") if a.strip()]
    return specs


@dataclass(frozen=True)
class ExcelRow:
    day: date
    focus: str
    exercise: str
    weight: float
    sets: int


def read_excel(path: Path) -> list[ExcelRow]:
    import openpyxl  # dev-only dependency: only this import script needs it

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows: list[ExcelRow] = []
    for values in workbook["Datenbank"].iter_rows(min_row=2, values_only=True):
        day, focus, exercise, weight, sets = (list(values) + [None] * 5)[:5]
        if not isinstance(day, datetime | date) or not exercise or weight is None:
            continue
        rows.append(
            ExcelRow(
                day=day.date() if isinstance(day, datetime) else day,
                focus=focus_from_label(str(focus)),
                exercise=str(exercise).strip(),
                weight=float(str(weight)),
                sets=int(str(sets)) if sets is not None else 3,
            )
        )
    workbook.close()
    return rows


@dataclass
class ImportReport:
    exercises_created: int = 0
    exercises_updated: int = 0
    inactive_exercises: list[str] = field(default_factory=list)
    sessions_created: int = 0
    sessions_skipped: int = 0


def import_training(
    db: Session, specs: dict[str, ExerciseSpec], rows: list[ExcelRow]
) -> ImportReport:
    report = ImportReport()
    by_name = {e.name: e for e in db.scalars(select(Exercise))}

    for spec in specs.values():
        exercise = by_name.get(spec.name)
        if exercise is None:
            exercise = Exercise(name=spec.name)
            db.add(exercise)
            by_name[spec.name] = exercise
            report.exercises_created += 1
        else:
            report.exercises_updated += 1
        exercise.focus = spec.focus
        exercise.position = spec.position
        exercise.kind = spec.kind
        exercise.muscle = spec.muscle
        exercise.default_sets = spec.default_sets
        exercise.gear_setting = spec.gear_setting
        exercise.caution = "; ".join(dict.fromkeys(spec.cautions)) or None
        exercise.aliases = list(dict.fromkeys(spec.aliases))
        exercise.unit = "min" if "plank" in spec.name.casefold() else "kg"
        exercise.is_active = True

    # Exercises that appear in the history but are no longer in the plan: keep them, inactive.
    for row in rows:
        if row.exercise not in by_name:
            legacy = Exercise(name=row.exercise, focus=row.focus, is_active=False, aliases=[])
            db.add(legacy)
            by_name[row.exercise] = legacy
            report.inactive_exercises.append(row.exercise)
    db.flush()

    existing = {(s.date, s.focus) for s in db.scalars(select(TrainingSession))}
    grouped: dict[tuple[date, str], list[ExcelRow]] = {}
    for row in rows:
        grouped.setdefault((row.day, row.focus), []).append(row)
    for (day, focus), session_rows in sorted(grouped.items()):
        if (day, focus) in existing:
            report.sessions_skipped += 1
            continue
        db.add(
            TrainingSession(
                date=day,
                focus=focus,
                entries=[
                    TrainingEntry(
                        exercise_id=by_name[row.exercise].id,
                        position=index,
                        weight=row.weight,
                        sets=row.sets,
                    )
                    for index, row in enumerate(session_rows)
                ],
            )
        )
        report.sessions_created += 1
    db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("context_md", type=Path)
    parser.add_argument("excel", type=Path)
    args = parser.parse_args()

    from mgpa_backend.db import SessionLocal

    specs = parse_context(args.context_md.read_text(encoding="utf-8"))
    rows = read_excel(args.excel)
    with SessionLocal() as db:
        report = import_training(db, specs, rows)
    print(
        f"Exercises: {report.exercises_created} created, {report.exercises_updated} updated, "
        f"{len(set(report.inactive_exercises))} inactive from history "
        f"({', '.join(sorted(set(report.inactive_exercises))) or '-'})\n"
        f"Sessions: {report.sessions_created} imported, {report.sessions_skipped} already present"
    )


if __name__ == "__main__":
    main()
