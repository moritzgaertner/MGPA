"""API schemas: the shape of JSON going in (requests) and out (responses).

Kept separate from the ORM models on purpose: the database structure can change
without silently changing the public API, and internal columns are never leaked.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from mgpa_backend.models import MessageRole


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
