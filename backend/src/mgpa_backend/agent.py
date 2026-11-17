"""The chat agent: Claude via Pydantic AI, plus conversion of stored messages into its history."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from anthropic import AsyncAnthropic
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError
from pydantic_ai import (
    Agent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRetry,
    RunContext,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from mgpa_backend import actions
from mgpa_backend.actions import NoteProposal
from mgpa_backend.config import get_settings
from mgpa_backend.knowledge.embeddings import EmbeddingsNotConfiguredError
from mgpa_backend.knowledge.search import SearchHit
from mgpa_backend.models import Action, Message, MessageRole, Note
from mgpa_backend.tracking import service as tracking_service
from mgpa_backend.tracking import tools as tracking_tools
from mgpa_backend.training import service as training_service
from mgpa_backend.training import tools as training_tools
from mgpa_backend.training.tools import TrainingEntryInput


def make_claude_model() -> AnthropicModel:
    """The Claude model used by all agents. Model ID and API key come from the settings (.env).

    The Anthropic SDK can emit its own OpenTelemetry spans; Pydantic AI already traces every
    model call, so the SDK's spans are switched off — otherwise Langfuse counts each call twice.
    """
    settings = get_settings()
    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(), open_telemetry=False
    )
    return AnthropicModel(
        settings.anthropic_model, provider=AnthropicProvider(anthropic_client=client)
    )


INSTRUCTIONS = """\
You are MGPA, a personal assistant for a single user: a master's student in Management & \
Technology who is applying for engineering roles.
Answer in the language the user writes in. Be concise and concrete; use Markdown when it helps.
If you don't know something, say so instead of guessing.

The user keeps personal documents (notes, CV, application material, plans) in a knowledge base. \
When a question may be answered by them, call `search_knowledge` before answering. Base such \
answers on the returned passages and cite each one you use as *(Source: <source>)*. If the \
passages don't contain the answer, say so.

You cannot write data directly. To save something (e.g. "notier dir …", "merk dir …"), call a \
`propose_*` tool: the user sees a card and confirms or discards it in the app. Never say that \
something is saved — say it is ready to confirm. Use `find_notes` to look up saved notes.

Training: the user logs workouts in short form, e.g. "BP 77, Skull 35, KB 15" (weights in kg; \
abbreviations are resolved by the tools; sets default to the exercise's usual number). Log them \
with `propose_training_log` (date defaults to today; resolve "gestern" etc. yourself). For \
"Briefing Brust", "heute Rücken", "heute Beine" or "what did I do last time" use \
`training_briefing` and present EVERY exercise in plan order with its last weight × sets and \
ALL machine settings (e.g. "Sitz 4 · Knie 3"), plus warnings — as a compact list. For progress \
of one exercise use `exercise_history`. Machines can have several named settings (e.g. \
Beinbeuger: Sitz, Knie, Fuß); record or change them with `propose_machine_settings`, passing \
only the settings the user mentioned.

Body weight and habits: "Gewicht 82,4" / "82.4 kg heute" -> `propose_weight`. "Habits: Lesen, \
Yoga" / "heute Vitamine und Mails erledigt" -> `propose_habit_checkin` with all named habits in \
one call. "Gym" is counted automatically from logged workouts; never tick it. For "wie läuft \
meine Woche", weight trend or habit progress use `tracking_overview`.\
"""

# Signature of the per-request search function the chat endpoint provides (see ChatContext).
KnowledgeSearch = Callable[[str], Awaitable[list[SearchHit]]]

# Upper bound for one answer. Only generated tokens are billed, so this is a safety cap,
# not a cost; long enough that normal answers are never cut off.
MAX_OUTPUT_TOKENS = 16_000


@dataclass
class PinnedNote:
    title: str
    content: str


@dataclass
class ChatContext:
    """Per-turn data the agent needs besides the history ("deps" in Pydantic AI terms)."""

    pinned_notes: list[PinnedNote] = field(default_factory=list)
    # Summary of older messages of this conversation that are no longer sent verbatim.
    summary: str | None = None
    # Searches the knowledge base with the request's DB session (None = no knowledge base).
    search_knowledge: KnowledgeSearch | None = None
    # The request's DB session and conversation, for tools that read notes or store proposals.
    db: Session | None = None
    conversation_id: int | None = None
    # Proposals created during this run, not yet streamed to the client.
    new_proposals: list[Action] = field(default_factory=list)
    # Claude may call several tools at once (e.g. weight + habits), and Pydantic AI runs them
    # concurrently. A SQLAlchemy session must not be used by two threads at the same time, so
    # all DB work of one chat turn goes through this lock, one tool after the other.
    db_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def in_db[T](self, fn: Callable[..., T], *args: Any) -> T:
        """Run a blocking DB function in a worker thread, never two at once for this turn."""
        async with self.db_lock:
            return await run_in_threadpool(fn, *args)


def render_pinned_notes(notes: Sequence[PinnedNote]) -> str:
    """System-prompt section with the user's pinned notes, verbatim."""
    if not notes:
        return ""
    sections = "\n\n".join(f"### {note.title}\n{note.content}" for note in notes)
    return (
        "## Pinned notes\n"
        "The user pinned these notes. They are always current and take precedence over older "
        "statements in the conversation. Follow them exactly (e.g. plans, numbers, schedules).\n\n"
        f"{sections}"
    )


def render_summary(summary: str | None) -> str:
    """System-prompt section with the summary of earlier, no longer included messages."""
    if not summary:
        return ""
    return (
        "## Summary of the earlier conversation\n"
        "Older messages of this conversation were condensed into this summary. Treat it as "
        "context you already know; pinned notes take precedence if they disagree.\n\n"
        f"{summary}"
    )


@lru_cache
def get_agent() -> Agent[ChatContext, str]:
    """Build the agent once. Model ID, API key and effort come from the settings (.env)."""
    settings = get_settings()
    agent = Agent(
        make_claude_model(),
        deps_type=ChatContext,
        instructions=INSTRUCTIONS,
        model_settings=AnthropicModelSettings(
            max_tokens=MAX_OUTPUT_TOKENS,
            anthropic_thinking={"type": "adaptive"},
            anthropic_effort=settings.anthropic_effort,
        ),
    )

    # Called on every run: adds the dynamic part of the system prompt after INSTRUCTIONS.
    @agent.instructions
    def pinned_notes_instructions(ctx: RunContext[ChatContext]) -> str:
        return render_pinned_notes(ctx.deps.pinned_notes)

    @agent.instructions
    def summary_instructions(ctx: RunContext[ChatContext]) -> str:
        return render_summary(ctx.deps.summary)

    @agent.tool
    async def search_knowledge(ctx: RunContext[ChatContext], query: str) -> str:
        """Search the user's knowledge base (their own notes, CV, application documents, plans).

        Args:
            query: What to look for, phrased as a short question or keywords.
        """
        async with ctx.deps.db_lock:  # the search reads chunks with the request's DB session
            return await run_knowledge_search(ctx.deps.search_knowledge, query)

    @agent.tool
    async def propose_note(
        ctx: RunContext[ChatContext], title: str, content: str, pinned: bool = False
    ) -> str:
        """Propose saving a note. Nothing is saved until the user confirms it in the app.

        Args:
            title: A short title (max 200 characters).
            content: The note text, keeping the user's own wording.
            pinned: True only if the user wants it pinned (included in every chat).
        """
        try:
            payload = NoteProposal(title=title, content=content, is_pinned=pinned)
        except ValidationError as error:
            raise ModelRetry(f"Invalid note: {error}") from error
        return await propose_action(ctx.deps, "create_note", payload)

    @agent.tool
    async def find_notes(ctx: RunContext[ChatContext], query: str) -> str:
        """Find saved notes whose title or text contains the query (case-insensitive).

        Args:
            query: A word or phrase to look for; use "" to list the most recent notes.
        """
        if ctx.deps.db is None:
            return "Notes are not available."
        return await ctx.deps.in_db(search_notes, ctx.deps.db, query)

    @agent.instructions
    def today_instructions() -> str:
        return f"Today is {training_tools.today():%A, %Y-%m-%d} ({settings.timezone})."

    @agent.tool
    async def training_briefing(ctx: RunContext[ChatContext], focus: str = "") -> str:
        """Training plan for a focus with last weights × sets, machine settings and warnings.

        Args:
            focus: e.g. "Brust", "Rücken", "Beine"; empty for an overview of all focuses.
        """
        if ctx.deps.db is None:
            return "Training data is not available."
        return await ctx.deps.in_db(training_service.training_overview, ctx.deps.db, focus)

    @agent.tool
    async def exercise_history(ctx: RunContext[ChatContext], exercise: str) -> str:
        """The latest entries (date, weight × sets) of one exercise, newest first.

        Args:
            exercise: Exercise name or abbreviation.
        """
        db = ctx.deps.db
        if db is None:
            return "Training data is not available."
        found = await ctx.deps.in_db(training_service.resolve_exercise, db, exercise)
        if found is None:
            suggestions = await ctx.deps.in_db(training_service.suggest_exercises, db, exercise)
            raise ModelRetry(f"Unknown exercise '{exercise}'. Did you mean: {suggestions}?")
        return await ctx.deps.in_db(training_service.exercise_history, db, found)

    @agent.tool
    async def propose_training_log(
        ctx: RunContext[ChatContext],
        entries: list[TrainingEntryInput],
        date: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Propose logging a workout. Nothing is saved until the user confirms it in the app.

        Args:
            entries: The exercises with weight (and sets only if the user gave them).
            date: Workout date as YYYY-MM-DD; omit for today.
            notes: Optional remarks, e.g. "aborted after butterfly" or "shoulder hurt".
        """
        db = ctx.deps.db
        if db is None:
            return "Saving is not available in this context."
        try:
            day = training_tools.parse_day(date)
            payload = await ctx.deps.in_db(
                training_tools.build_training_proposal, db, entries, day, notes
            )
        except (ValueError, ValidationError) as error:  # incl. UnknownExerciseError
            raise ModelRetry(str(error)) from error
        return await propose_action(ctx.deps, "log_training", payload)

    @agent.tool
    async def propose_machine_settings(
        ctx: RunContext[ChatContext],
        exercise: str,
        settings: dict[str, str],
        replace: bool = False,
    ) -> str:
        """Propose recording or changing machine settings of an exercise. Needs confirmation.

        Args:
            exercise: Exercise name or abbreviation.
            settings: Named settings, e.g. {"Sitz": "4", "Knie": "3", "Fuß": "2"}. Use
                {"Einstellung": "..."} for a machine with a single setting. Only the given
                names change, the others stay; an empty value removes that setting.
            replace: True only if the user wants to replace ALL settings with the given ones.
        """
        db = ctx.deps.db
        if db is None:
            return "Saving is not available in this context."
        try:
            payload = await ctx.deps.in_db(
                training_tools.build_settings_proposal, db, exercise, settings, replace
            )
        except (ValueError, ValidationError) as error:
            raise ModelRetry(str(error)) from error
        return await propose_action(ctx.deps, "update_machine_settings", payload)

    @agent.tool
    async def tracking_overview(ctx: RunContext[ChatContext]) -> str:
        """Body weight trend (latest, 7-day averages) and this week's habit progress vs. goals."""
        if ctx.deps.db is None:
            return "Tracking data is not available."
        return await ctx.deps.in_db(
            tracking_service.tracking_overview, ctx.deps.db, training_tools.today()
        )

    @agent.tool
    async def propose_weight(
        ctx: RunContext[ChatContext], weight: float, date: str | None = None
    ) -> str:
        """Propose logging body weight. Nothing is saved until the user confirms it in the app.

        Args:
            weight: Body weight in kg, e.g. 82.4.
            date: YYYY-MM-DD; omit for today.
        """
        db = ctx.deps.db
        if db is None:
            return "Saving is not available in this context."
        try:
            day = training_tools.parse_day(date)
            payload = await ctx.deps.in_db(tracking_tools.build_weight_proposal, db, weight, day)
        except (ValueError, ValidationError) as error:
            raise ModelRetry(str(error)) from error
        return await propose_action(ctx.deps, "log_weight", payload)

    @agent.tool
    async def propose_habit_checkin(
        ctx: RunContext[ChatContext], habits: list[str], date: str | None = None
    ) -> str:
        """Propose ticking off habits as done. Nothing is saved until the user confirms it.

        Args:
            habits: Habit names as the user wrote them, e.g. ["Lesen", "Yoga"].
            date: YYYY-MM-DD; omit for today.
        """
        db = ctx.deps.db
        if db is None:
            return "Saving is not available in this context."
        try:
            day = training_tools.parse_day(date)
            payload = await ctx.deps.in_db(tracking_tools.build_habit_proposal, db, habits, day)
        except (ValueError, ValidationError) as error:
            raise ModelRetry(str(error)) from error
        return await propose_action(ctx.deps, "check_habits", payload)

    return agent


async def propose_action(deps: ChatContext, kind: str, payload: BaseModel) -> str:
    """Store a proposal and queue it for the client. Returns the tool result for Claude."""
    if deps.db is None or deps.conversation_id is None:
        return "Saving is not available in this context."
    action = await deps.in_db(actions.propose, deps.db, deps.conversation_id, kind, payload)
    deps.new_proposals.append(action)
    return (
        f"Proposal #{action.id} ({action.label}) is shown to the user. "
        "Nothing is saved until they confirm it."
    )


def search_notes(db: Session, query: str, limit: int = 10) -> str:
    """Tool result listing matching notes, newest first."""
    stmt = select(Note).order_by(Note.updated_at.desc(), Note.id.desc()).limit(limit)
    if query.strip():
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(or_(Note.title.ilike(pattern), Note.content.ilike(pattern)))
    notes = db.scalars(stmt).all()
    if not notes:
        return "No notes found."
    return "\n\n".join(
        f"### {note.title}{' (pinned)' if note.is_pinned else ''} — "
        f"updated {note.updated_at:%Y-%m-%d}\n{note.content}"
        for note in notes
    )


async def run_knowledge_search(search: KnowledgeSearch | None, query: str) -> str:
    """Tool result for Claude: numbered passages with their source, or a short explanation."""
    if search is None:
        return "The knowledge base is not available."
    try:
        hits = await search(query)
    except EmbeddingsNotConfiguredError:
        return "The knowledge base is not configured (no embedding API key)."
    if not hits:
        return "No relevant passages found in the knowledge base."
    return "\n\n".join(
        f"[{number}] Source: {hit.source}\n{hit.content}" for number, hit in enumerate(hits, 1)
    )


def to_model_history(messages: Sequence[Message]) -> list[ModelMessage]:
    """Translate our stored messages into the format Pydantic AI sends to Claude as history."""
    history: list[ModelMessage] = []
    for message in messages:
        if message.role == MessageRole.USER:
            history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=message.content)]))
    return history
