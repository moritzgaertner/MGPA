"""Training: CONTEXT.md parsing, import, exercise resolution and briefings (synthetic data)."""

from datetime import date

from sqlalchemy.orm import Session

from mgpa_backend.models import Exercise, TrainingSession
from mgpa_backend.training.importer import ExcelRow, import_training, parse_context
from mgpa_backend.training.service import (
    exercise_history,
    resolve_exercise,
    suggest_exercises,
    training_overview,
)

CONTEXT = """\
# Context

## Trainingsplan: 2er Split

### TAG X — Push (`1 - Pushday`)
| # | Übung | Typ | Muskel |
|---|---|---|---|
| 1 | Test Press | Compound | Brust |
| 2 | Test Raise | Isolation | Schulter |

### TAG Y — Legs (`2 - Legday`)
| # | Übung | Typ | Muskel |
|---|---|---|---|
| 1 | Test Squat | Compound | Beine | ⚠️ immer 2 Arbeitssätze |
| 2 | Test Plank | Isolation | Core |

## Abkürzungsschlüssel

| Kürzel | Übung |
|---|---|
| TP / T Press | Test Press |
| SQ | Test Squat |

## Geräteeinstellungen

### TAG X
| Übung | Einstellung |
|---|---|
| Test Press | Stufe 3 |
| Test Raise | — | ⚠️ Schulter schonen |
"""

ROWS = [
    ExcelRow(date(2026, 3, 1), "Pushday", "Test Press", 60, 3),
    ExcelRow(date(2026, 3, 1), "Pushday", "Test Raise", 10, 3),
    ExcelRow(date(2026, 3, 1), "Pushday", "Old Fly", 12, 3),  # not in the plan anymore
    ExcelRow(date(2026, 3, 8), "Pushday", "Test Press", 62.5, 3),
    ExcelRow(date(2026, 3, 4), "Legday", "Test Squat", 20, 2),
    ExcelRow(date(2026, 3, 4), "Legday", "Test Plank", 2.25, 2),
]


def test_parse_context_reads_plan_settings_and_aliases() -> None:
    specs = parse_context(CONTEXT)

    press, raise_, squat = specs["Test Press"], specs["Test Raise"], specs["Test Squat"]
    assert (press.focus, press.position, press.kind, press.muscle) == (
        "Pushday",
        1,
        "Compound",
        "Brust",
    )
    assert press.gear_setting == "Stufe 3" and press.aliases == ["TP", "T Press"]
    assert raise_.gear_setting is None and raise_.cautions == ["Schulter schonen"]
    assert squat.default_sets == 2 and squat.focus == "Legday"


def test_import_creates_exercises_sessions_and_is_rerunnable(db: Session) -> None:
    specs = parse_context(CONTEXT)

    report = import_training(db, specs, ROWS)
    again = import_training(db, specs, ROWS)

    assert report.sessions_created == 3 and again.sessions_created == 0
    assert again.sessions_skipped == 3
    assert report.inactive_exercises == ["Old Fly"]
    old = db.query(Exercise).filter_by(name="Old Fly").one()
    assert old.is_active is False
    plank = db.query(Exercise).filter_by(name="Test Plank").one()
    assert plank.unit == "min"
    session = db.query(TrainingSession).filter_by(date=date(2026, 3, 4)).one()
    assert [(e.exercise.name, e.weight, e.sets) for e in session.entries] == [
        ("Test Squat", 20.0, 2),
        ("Test Plank", 2.25, 2),
    ]


def test_resolve_exercise_by_name_or_alias(db: Session) -> None:
    import_training(db, parse_context(CONTEXT), ROWS)

    assert resolve_exercise(db, "tp") is not None
    assert resolve_exercise(db, "T. Press").name == "Test Press"  # type: ignore[union-attr]
    assert resolve_exercise(db, "Test squat").name == "Test Squat"  # type: ignore[union-attr]
    assert resolve_exercise(db, "Bench") is None
    assert "Test Press" in suggest_exercises(db, "Test Pres")


def test_overview_shows_last_values_settings_and_skipped(db: Session) -> None:
    import_training(db, parse_context(CONTEXT), ROWS)

    text = training_overview(db, "pushday")

    assert "last session 08.03.2026" in text
    assert "1. Test Press: 62.5 kg × 3 (setting: Stufe 3)" in text
    # Test Raise was not done on 08.03., its last value is from 01.03.
    assert (
        "2. Test Raise: 10 kg × 3 (from 01.03.2026, skipped last time; ⚠️ Schulter schonen)" in text
    )
    assert "Old Fly" not in text  # inactive


def test_overview_without_focus_lists_focuses(db: Session) -> None:
    import_training(db, parse_context(CONTEXT), ROWS)

    text = training_overview(db, "")

    assert "Legday" in text and "Pushday" in text


def test_history_newest_first_with_unit(db: Session) -> None:
    import_training(db, parse_context(CONTEXT), ROWS)

    press = resolve_exercise(db, "TP")
    plank = resolve_exercise(db, "Test Plank")
    assert press is not None and plank is not None

    assert exercise_history(db, press).splitlines()[1:] == [
        "- 08.03.2026: 62.5 kg × 3",
        "- 01.03.2026: 60 kg × 3",
    ]
    assert "2.25 min × 2" in exercise_history(db, plank)
