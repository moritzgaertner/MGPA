"""API schemas: the shape of JSON going in (requests) and out (responses).

Kept separate from the ORM models on purpose: the database structure can change
without silently changing the public API, and internal columns are never leaked.
"""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mgpa_backend.models import MessageRole

# Pinned notes are sent with every chat turn, so their size directly drives token cost.
NOTE_CONTENT_MAX_CHARS = 10_000


class ConversationCreate(BaseModel):
    """Request body for POST /conversations. The title is optional."""

    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    """Request body for PATCH /conversations/{id}."""

    title: str = Field(min_length=1, max_length=200)


class MessageRead(BaseModel):
    """One message as returned by the API."""

    # from_attributes: allow building this schema directly from an ORM object
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    """A conversation without its messages, used in lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    """A single conversation including all its messages, in order."""

    messages: list[MessageRead]


class NoteCreate(BaseModel):
    """Request body for POST /notes."""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=NOTE_CONTENT_MAX_CHARS)
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    """Request body for PATCH /notes/{id}. Only the fields that are sent get changed."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=NOTE_CONTENT_MAX_CHARS)
    is_pinned: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        """Leaving a field out means "keep it"; sending null is an error (columns are NOT NULL)."""
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self

    def changes(self) -> dict[str, Any]:
        """Only the fields the client actually sent."""
        return self.model_dump(exclude_unset=True)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    """Request body for POST /chat. Without conversation_id a new conversation is started."""

    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=20_000)


# --- Server-Sent Events emitted by POST /chat, in this order ------------------------------------


class ChatStartEvent(BaseModel):
    """event: start — which conversation the answer belongs to (new or existing)."""

    conversation_id: int


class ChatDeltaEvent(BaseModel):
    """event: delta — the next piece of the answer text."""

    text: str


class ChatDoneEvent(BaseModel):
    """event: done — the answer is complete and saved."""

    message_id: int
    input_tokens: int
    output_tokens: int


class ChatErrorEvent(BaseModel):
    """event: error — the model call failed; the user message stays saved."""

    detail: str
