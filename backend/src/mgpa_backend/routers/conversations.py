"""CRUD endpoints for conversations."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mgpa_backend.db import DbSession
from mgpa_backend.models import Conversation
from mgpa_backend.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_or_404(db: DbSession, conversation_id: int) -> Conversation:
    """Load a conversation or stop the request with 404 Not Found."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conversation(body: ConversationCreate, db: DbSession) -> ConversationRead:
    conversation = Conversation(title=body.title)
    db.add(conversation)
    db.commit()
    return ConversationRead.model_validate(conversation)


@router.get("")
def list_conversations(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ConversationRead]:
    """Most recently active first; id breaks ties between equal timestamps."""
    stmt = (
        select(Conversation)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
    )
    return [ConversationRead.model_validate(c) for c in db.scalars(stmt)]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, db: DbSession) -> ConversationDetail:
    # selectinload: fetch all messages in one extra query instead of lazily on first access
    conversation = db.get(
        Conversation, conversation_id, options=[selectinload(Conversation.messages)]
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationDetail.model_validate(conversation)


@router.patch("/{conversation_id}")
def rename_conversation(
    conversation_id: int, body: ConversationUpdate, db: DbSession
) -> ConversationRead:
    conversation = _get_or_404(db, conversation_id)
    conversation.title = body.title
    db.commit()
    return ConversationRead.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, db: DbSession) -> None:
    conversation = _get_or_404(db, conversation_id)
    db.delete(conversation)  # messages go with it (ON DELETE CASCADE)
    db.commit()
