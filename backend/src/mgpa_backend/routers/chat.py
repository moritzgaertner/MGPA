"""POST /chat: send a message, stream Claude's answer back as Server-Sent Events (SSE)."""

import logging
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.usage import RunUsage
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from mgpa_backend.agent import (
    ChatContext,
    KnowledgeSearch,
    PinnedNote,
    get_agent,
    to_model_history,
)
from mgpa_backend.db import DbSession
from mgpa_backend.knowledge.embeddings import get_embedder
from mgpa_backend.knowledge.search import SearchHit, search_chunks
from mgpa_backend.models import Action, Conversation, Message, MessageRole, Note
from mgpa_backend.observability import traced
from mgpa_backend.schemas import (
    ActionRead,
    ChatDeltaEvent,
    ChatDoneEvent,
    ChatErrorEvent,
    ChatProposalEvent,
    ChatRequest,
    ChatStartEvent,
    ChatToolEvent,
)
from mgpa_backend.summary import summarize_if_needed

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@dataclass
class ChatTurn:
    """Everything the streaming part needs, prepared before the stream starts."""

    conversation_id: int
    prompt: str
    history: list[ModelMessage]
    context: ChatContext


TITLE_MAX_CHARS = 60


def title_from_message(message: str) -> str:
    """Default title for a new conversation: its first message, on one line, shortened."""
    one_line = " ".join(message.split())
    if len(one_line) <= TITLE_MAX_CHARS:
        return one_line
    return one_line[: TITLE_MAX_CHARS - 1].rstrip() + "…"


def start_chat_turn(body: ChatRequest, db: DbSession) -> ChatTurn:
    """Load (or create) the conversation and save the user message.

    Runs as a dependency, i.e. BEFORE the response starts. Once an SSE stream has begun,
    the status code (200) is already sent — so a 404 must be raised here, not in the stream.
    """
    if body.conversation_id is None:
        conversation = Conversation(title=title_from_message(body.message))
        db.add(conversation)
    else:
        found = db.get(
            Conversation, body.conversation_id, options=[selectinload(Conversation.messages)]
        )
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        conversation = found

    # History = messages not yet covered by the summary, WITHOUT the new message (= the prompt).
    already_summarized = conversation.summarized_until_id or 0
    history = to_model_history([m for m in conversation.messages if m.id > already_summarized])

    # Save the user message right away, so it is not lost if the model call fails.
    conversation.messages.append(Message(role=MessageRole.USER, content=body.message))
    conversation.updated_at = func.now()  # the database fills in its own current time
    db.commit()

    # Pinned notes, oldest first, so their order in the system prompt stays stable.
    pinned = db.scalars(select(Note).where(Note.is_pinned).order_by(Note.id)).all()
    context = ChatContext(
        pinned_notes=[PinnedNote(n.title, n.content) for n in pinned],
        summary=conversation.summary,
    )

    return ChatTurn(
        conversation_id=conversation.id, prompt=body.message, history=history, context=context
    )


def _save_answer(db: Session, conversation_id: int, text: str) -> int:
    """Persist the assistant's complete answer and bump the conversation's updated_at."""
    message = Message(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=text)
    db.add(message)
    db.flush()
    # Attach the proposals made during this answer to it, so they render under it after reload.
    db.execute(
        update(Action)
        .where(Action.conversation_id == conversation_id, Action.message_id.is_(None))
        .values(message_id=message.id)
    )
    db.execute(
        update(Conversation).where(Conversation.id == conversation_id).values(updated_at=func.now())
    )
    db.commit()
    return message.id


def make_knowledge_search(db: Session) -> KnowledgeSearch:
    """Knowledge search bound to this request's DB session (so tests see their own data)."""

    async def search(query: str) -> list[SearchHit]:
        # Both steps block (HTTP call to Voyage, SQL query): run them in worker threads.
        embedding = await run_in_threadpool(get_embedder().embed_query, query)
        return await run_in_threadpool(search_chunks, db, embedding)

    return search


@router.post("/chat", response_class=EventSourceResponse)
async def chat(
    turn: Annotated[ChatTurn, Depends(start_chat_turn)], db: DbSession
) -> AsyncIterable[ServerSentEvent]:
    """Stream the answer: `start`, then `delta` text pieces and `tool` notices, then `done`
    (or `error`).

    Uses run_stream_events (not run_stream): run_stream would end at the first text the model
    writes, so a tool call after "Let me check…" would never run.
    """
    yield ServerSentEvent(data=ChatStartEvent(conversation_id=turn.conversation_id), event="start")
    turn.context.search_knowledge = make_knowledge_search(db)
    turn.context.db = db
    turn.context.conversation_id = turn.conversation_id

    parts: list[str] = []
    usage: RunUsage | None = None
    try:
        with traced("chat", turn.conversation_id, tags=["chat"]):
            async with get_agent().run_stream_events(
                turn.prompt, message_history=turn.history, deps=turn.context
            ) as events:
                async for event in events:
                    # Proposals stored by a tool since the last event: show them right away.
                    while turn.context.new_proposals:
                        action = turn.context.new_proposals.pop(0)
                        yield ServerSentEvent(
                            data=ChatProposalEvent(action=ActionRead.model_validate(action)),
                            event="proposal",
                        )
                    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                        # A new text block (e.g. after a tool call): separate it from the last.
                        piece = ("\n\n" if parts else "") + event.part.content
                    elif isinstance(event, PartDeltaEvent) and isinstance(
                        event.delta, TextPartDelta
                    ):
                        piece = event.delta.content_delta
                    elif isinstance(event, FunctionToolCallEvent):
                        yield ServerSentEvent(
                            data=ChatToolEvent(
                                name=event.part.tool_name, args=event.part.args_as_dict()
                            ),
                            event="tool",
                        )
                        continue
                    elif isinstance(event, AgentRunResultEvent):
                        usage = event.result.usage
                        continue
                    else:
                        continue
                    if piece:
                        parts.append(piece)
                        yield ServerSentEvent(data=ChatDeltaEvent(text=piece), event="delta")
        if usage is None:
            raise RuntimeError("Agent run ended without a result")
    except Exception:
        # Full details go to the server log; the client only gets a generic message.
        logger.exception("Model call failed for conversation %s", turn.conversation_id)
        yield ServerSentEvent(
            data=ChatErrorEvent(detail="The assistant could not answer. Please try again."),
            event="error",
        )
        return

    # Database calls block; run them in a worker thread so the server stays responsive.
    message_id = await run_in_threadpool(_save_answer, db, turn.conversation_id, "".join(parts))
    yield ServerSentEvent(
        data=ChatDoneEvent(
            message_id=message_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        ),
        event="done",
    )

    # After `done`, so the user never waits for it. If the client disconnects first, this is
    # skipped — harmless, the next turn is still over the threshold and tries again.
    await summarize_if_needed(db, turn.conversation_id, usage.input_tokens)
