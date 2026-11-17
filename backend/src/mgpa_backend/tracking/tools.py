"""Turn the agent's tool arguments into validated weight / habit proposals (no LLM logic here)."""

from datetime import date

from sqlalchemy.orm import Session

from mgpa_backend.actions import HabitCheckinProposal, HabitRef, WeightProposal
from mgpa_backend.models import HabitSource
from mgpa_backend.tracking.service import (
    active_habits,
    resolve_habit,
    suggest_habits,
    weight_on,
)


def build_weight_proposal(db: Session, weight: float, day: date) -> WeightProposal:
    return WeightProposal(date=day, weight=weight, previous=weight_on(db, day))


def build_habit_proposal(db: Session, names: list[str], day: date) -> HabitCheckinProposal:
    refs: list[HabitRef] = []
    for name in names:
        habit = resolve_habit(db, name)
        if habit is None:
            suggestions = suggest_habits(db, name)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            known = ", ".join(h.name for h in active_habits(db))
            raise ValueError(
                f"Unknown habit '{name}'.{hint} Known habits: {known}. "
                "If none fits, ask the user instead of guessing."
            )
        if habit.source == HabitSource.TRAINING:
            raise ValueError(
                f"'{habit.name}' is counted automatically from logged training sessions — "
                "leave it out (log the workout with propose_training_log instead)."
            )
        if all(ref.habit_id != habit.id for ref in refs):
            refs.append(HabitRef(habit_id=habit.id, name=habit.name))
    if not refs:
        raise ValueError("No habits given.")
    return HabitCheckinProposal(date=day, habits=refs)
