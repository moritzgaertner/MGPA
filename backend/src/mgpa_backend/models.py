"""ORM models: every class here becomes one table in Postgres."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mgpa_backend.db import Base


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Postgres enum column type that stores the values ("user"), not the member names ("USER")."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class TimestampMixin:
    """Adds created_at/updated_at, both set by the database. Mixed into most models."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Chat ---------------------------------------------------------------------------------------


class MessageRole(StrEnum):
    """Who wrote a message. Stored as a Postgres enum, so typos are rejected."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(TimestampMixin, Base):
    """One chat thread. updated_at is touched by the chat endpoint on every new message."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Empty at first; a title can be generated from the first message later.
    title: Mapped[str | None] = mapped_column(String(200))

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        # Deleting a conversation deletes its messages; the database does it (passive_deletes).
        cascade="all, delete-orphan",
        passive_deletes=True,
        # Order by id, not created_at: messages saved in one transaction share the same now().
        order_by="Message.id",
    )


class Message(Base):
    """One message inside a conversation. Messages are never edited, so no updated_at."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(pg_enum(MessageRole, "message_role"))
    # Chat messages can be arbitrarily long, so Text instead of String(n).
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


# --- Notes & tasks (agent tools in M5) ----------------------------------------------------------


class Note(TimestampMixin, Base):
    """A free-text note, created by me or proposed by the agent."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)


class Task(TimestampMixin, Base):
    """A to-do item. Open tasks feed the daily briefing (M6)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    # Date only (no time): "due on 24 Oct" is enough for a personal to-do list.
    due_date: Mapped[date | None] = mapped_column(Date)
    # server_default so rows inserted outside Python (SQL, Dagster) are also "open".
    is_done: Mapped[bool] = mapped_column(default=False, server_default=false())


# --- Knowledge base (ingestion in M4; chunks table follows with the embedding model) ------------


class DocumentStatus(StrEnum):
    """Lifecycle of an uploaded file through the Dagster ingestion pipeline."""

    PENDING = "pending"  # uploaded, waiting for Dagster
    PROCESSING = "processing"  # Dagster is parsing/chunking/embedding
    READY = "ready"  # searchable via search_knowledge
    FAILED = "failed"  # see `error`


class Document(TimestampMixin, Base):
    """An uploaded PDF or Markdown file. The file itself lives on disk, not in the database."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Original name as uploaded, shown in the UI and in citations.
    filename: Mapped[str] = mapped_column(String(255))
    # MIME type, e.g. "application/pdf" or "text/markdown"; decides which parser Dagster uses.
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    # Fingerprint of the file content; unique, so the same file cannot be ingested twice.
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    # Where the API stored the file on the shared volume (relative path).
    storage_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"),
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
    )
    # Error message if status == failed, so the UI can show why.
    error: Mapped[str | None] = mapped_column(Text)
