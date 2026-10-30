"""POST /chat: send a message, stream Claude's answer back as Server-Sent Events (SSE)."""

import logging
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic_ai import ModelMessage
from sqlalchemy import func, update
from sqlalchemy.orm import Session, selectinload

from mgpa_backend.agent import get_agent, to_model_history
from mgpa_backend.db import DbSession
from mgpa_backend.models import Conversation, Message, MessageRole
from mgpa_backend.schemas import (
    ChatDeltaEvent,
    ChatDoneEvent,
    ChatErrorEvent,
    ChatRequest,
    ChatStartEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@dataclass
class ChatTurn:
    """Everything the streaming part needs, prepared before the stream starts."""

    conversation_id: int
    prompt: str
    history: list[ModelMessage]


def start_chat_turn(body: ChatRequest, db: DbSession) -> ChatTurn:
    """Load (or create) the conversation and save the user message.

    Runs as a dependency, i.e. BEFORE the response starts. Once an SSE stream has begun,
    the status code (200) is already sent — so a 404 must be raised here, not in the stream.
    """
    if body.conversation_id is None:
        conversation = Conversation()
        db.add(conversation)
    else:
        found = db.get(
            Conversation, body.conversation_id, options=[selectinload(Conversation.messages)]
        )
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        conversation = found

    # History = everything said so far, WITHOUT the new message (that one is the prompt).
    history = to_model_history(conversation.messages)

    # Save the user message right away, so it is not lost if the model call fails.
    conversation.messages.append(Message(role=MessageRole.USER, content=body.message))
    conversation.updated_at = func.now()  # the database fills in its own current time
    db.commit()

    return ChatTurn(conversation_id=conversation.id, prompt=body.message, history=history)


def _save_answer(db: Session, conversation_id: int, text: str) -> int:
    """Persist the assistant's complete answer and bump the conversation's updated_at."""
    message = Message(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=text)
    db.add(message)
    db.execute(
        update(Conversation).where(Conversation.id == conversation_id).values(updated_at=func.now())
    )
    db.commit()
    return message.id


@router.post("/chat", response_class=EventSourceResponse)
async def chat(
    turn: Annotated[ChatTurn, Depends(start_chat_turn)], db: DbSession
) -> AsyncIterable[ServerSentEvent]:
    """Stream the answer: one `start`, many `delta`, then `done` (or `error`)."""
    yield ServerSentEvent(data=ChatStartEvent(conversation_id=turn.conversation_id), event="start")

    parts: list[str] = []
    try:
        async with get_agent().run_stream(turn.prompt, message_history=turn.history) as result:
            async for delta in result.stream_text(delta=True):
                parts.append(delta)
                yield ServerSentEvent(data=ChatDeltaEvent(text=delta), event="delta")
            usage = result.usage
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
