"""The chat agent: Claude via Pydantic AI, plus conversion of stored messages into its history."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from pydantic_ai import (
    Agent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RunContext,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider

from mgpa_backend.config import get_settings
from mgpa_backend.models import Message, MessageRole

INSTRUCTIONS = """\
You are MGPA, a personal assistant for a single user: a master's student in Management & \
Technology who is applying for engineering roles.
Answer in the language the user writes in. Be concise and concrete; use Markdown when it helps.
If you don't know something, say so instead of guessing.\
"""

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
    model = AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
    agent = Agent(
        model,
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

    return agent


def to_model_history(messages: Sequence[Message]) -> list[ModelMessage]:
    """Translate our stored messages into the format Pydantic AI sends to Claude as history."""
    history: list[ModelMessage] = []
    for message in messages:
        if message.role == MessageRole.USER:
            history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=message.content)]))
    return history
