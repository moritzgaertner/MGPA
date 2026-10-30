"""Rolling conversation summary: keeps the context sent to Claude small in long chats.

Once a chat turn's input grows past a token threshold, the older messages are folded into a
running summary. Claude then receives "summary + the most recent messages" instead of the full
history. Nothing is deleted: all messages stay in the database and in the UI.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from fastapi.concurrency import run_in_threadpool
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider
from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.config import get_settings
from mgpa_backend.models import Conversation, Message, MessageRole

logger = logging.getLogger(__name__)

SUMMARY_INSTRUCTIONS = """\
You maintain a running summary of a chat between a user and their personal assistant.
You get the previous summary (may be empty) and the next part of the transcript.
Return ONE updated summary that replaces the previous one.

Keep: facts about the user, decisions, numbers and dates, agreed next steps, open questions,
and preferences on how the assistant should answer. Drop small talk and repetition.
Write in the language of the conversation, as compact bullet points, at most ~300 words.
Return only the summary, no preamble.\
"""


@lru_cache
def get_summarizer() -> Agent[None, str]:
    """A separate, tool-less agent for summarizing. Same model settings as the chat agent."""
    settings = get_settings()
    model = AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
    return Agent(
        model,
        instructions=SUMMARY_INSTRUCTIONS,
        model_settings=AnthropicModelSettings(
            max_tokens=4_000,
            anthropic_thinking={"type": "adaptive"},
            anthropic_effort="low",
        ),
    )


def fold_cutoff(messages: Sequence[Message], keep: int) -> int:
    """How many of the (oldest) `messages` to fold into the summary.

    Keeps at least the last `keep` messages verbatim, and moves the cut forward until the kept
    part starts with a user message, so the history sent to Claude never begins mid-exchange.
    Returns 0 if there is not enough to summarize.
    """
    cut = len(messages) - keep
    while 0 < cut < len(messages) and messages[cut].role != MessageRole.USER:
        cut += 1
    return cut if cut >= 2 else 0


def format_transcript(messages: Sequence[Message]) -> str:
    speaker = {MessageRole.USER: "User", MessageRole.ASSISTANT: "Assistant"}
    return "\n\n".join(f"{speaker[m.role]}: {m.content}" for m in messages)


@dataclass
class FoldPlan:
    """What to summarize, loaded from the database before calling the model."""

    previous_summary: str | None
    transcript: str
    last_folded_id: int


def _plan_fold(db: Session, conversation_id: int, keep: int) -> FoldPlan | None:
    conversation = db.get_one(Conversation, conversation_id)
    unsummarized = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.id > (conversation.summarized_until_id or 0),
        )
        .order_by(Message.id)
    ).all()
    cut = fold_cutoff(unsummarized, keep)
    if cut == 0:
        return None
    to_fold = unsummarized[:cut]
    return FoldPlan(
        previous_summary=conversation.summary,
        transcript=format_transcript(to_fold),
        last_folded_id=to_fold[-1].id,
    )


def _save_summary(db: Session, conversation_id: int, summary: str, last_folded_id: int) -> None:
    conversation = db.get_one(Conversation, conversation_id)
    conversation.summary = summary
    conversation.summarized_until_id = last_folded_id
    db.commit()


async def summarize_if_needed(db: Session, conversation_id: int, input_tokens: int) -> bool:
    """Fold older messages into the summary if the last turn's input was too large.

    Never raises: a failed summary only means the next turn sends the full history again,
    and the next turn will simply try again. Returns True if a new summary was saved.
    """
    settings = get_settings()
    if input_tokens <= settings.summary_trigger_tokens:
        return False
    try:
        plan = await run_in_threadpool(
            _plan_fold, db, conversation_id, settings.summary_keep_messages
        )
        if plan is None:
            return False
        prompt = (
            f"Previous summary:\n{plan.previous_summary or '(none)'}\n\n"
            f"Next part of the transcript:\n{plan.transcript}"
        )
        result = await get_summarizer().run(prompt)
        await run_in_threadpool(
            _save_summary, db, conversation_id, result.output, plan.last_folded_id
        )
    except Exception:
        logger.exception("Summarizing conversation %s failed", conversation_id)
        return False
    logger.info("Conversation %s summarized up to message %s", conversation_id, plan.last_folded_id)
    return True
