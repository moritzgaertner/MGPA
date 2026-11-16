"""ORM models: every class here becomes one table in Postgres."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    # Running summary of older messages. Claude gets "summary + messages after
    # summarized_until_id" instead of the full history; all messages stay in the database.
    summary: Mapped[str | None] = mapped_column(Text)
    summarized_until_id: Mapped[int | None]

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
    # Proposals the assistant made in this message (shown as confirm/discard cards).
    actions: Mapped[list["Action"]] = relationship(
        back_populates="message", passive_deletes=True, order_by="Action.id"
    )


# --- Human-in-the-loop actions -----------------------------------------------------------------


class ActionStatus(StrEnum):
    PROPOSED = "proposed"  # waiting for the user
    CONFIRMED = "confirmed"  # executed
    REJECTED = "rejected"  # discarded by the user


class Action(Base):
    """A write action the assistant proposed (e.g. "save note X"). Nothing is written until the
    user confirms; then the backend executes it directly (see actions.py)."""

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # The assistant message that made the proposal (set once the answer is saved).
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    # Action type, e.g. "create_note". A plain string (not a DB enum), so new action types
    # need no migration — valid kinds are defined in code (actions.REGISTRY).
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Human-readable proposal, e.g. "Save note “Shopping list”".
    label: Mapped[str] = mapped_column(String(300))
    status: Mapped[ActionStatus] = mapped_column(
        pg_enum(ActionStatus, "action_status"),
        default=ActionStatus.PROPOSED,
        server_default=ActionStatus.PROPOSED.value,
    )
    # What happened on confirm, e.g. "Note “Shopping list” saved", and the created row's id.
    result_summary: Mapped[str | None] = mapped_column(Text)
    result_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    message: Mapped[Message | None] = relationship(back_populates="actions")


# --- Notes & tasks (agent tools in M5) ----------------------------------------------------------


class Note(TimestampMixin, Base):
    """A free-text note, created by me or proposed by the agent."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    # Pinned notes (e.g. a training plan) go into the system prompt of EVERY chat turn,
    # word for word — they are never summarized away. They cost input tokens on every turn.
    is_pinned: Mapped[bool] = mapped_column(default=False, server_default=false())


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


# --- Knowledge base (ingested by the Dagster pipeline in /pipelines) ----------------------------

# Vector size of the embedding model (Voyage voyage-4 family at output_dimension=1024).
# Changing it requires a migration AND re-embedding every chunk.
EMBEDDING_DIMENSIONS = 1024


class DocumentStatus(StrEnum):
    """Lifecycle of an uploaded file through the Dagster ingestion pipeline."""

    PENDING = "pending"  # uploaded, waiting for Dagster
    PROCESSING = "processing"  # Dagster is parsing/chunking/embedding
    READY = "ready"  # searchable via search_knowledge
    FAILED = "failed"  # see `error`


class Document(TimestampMixin, Base):
    """An uploaded Markdown or plain-text file. The file itself lives on disk, not in the DB."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Original name as uploaded, shown in the UI and in citations.
    filename: Mapped[str] = mapped_column(String(255))
    # MIME type: "text/markdown" or "text/plain" (Markdown gets heading-aware chunking).
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
    # Number of chunks once ingested (null until then).
    chunk_count: Mapped[int | None]

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    """A searchable piece of a document: its text, where it came from, and its embedding."""

    __tablename__ = "chunks"
    __table_args__ = (
        # Each position exists once per document.
        UniqueConstraint("document_id", "chunk_index"),
        # Approximate nearest-neighbour index (HNSW) for cosine similarity searches.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # Position within the document (0, 1, 2, ...), for ordering and citations.
    chunk_index: Mapped[int]
    # Markdown heading path, e.g. "Training › Day B" — shown in citations. Null for plain text.
    heading: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")


# --- Training ----------------------------------------------------------------------------------


class Exercise(TimestampMixin, Base):
    """An exercise in the training plan, incl. machine settings and abbreviations for parsing."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Training focus / day, e.g. "Brust", "Rücken", "Beine".
    focus: Mapped[str] = mapped_column(String(50), index=True)
    muscle: Mapped[str | None] = mapped_column(String(50))
    kind: Mapped[str | None] = mapped_column(String(20))  # "Compound" / "Isolation"
    # Order within its focus (1, 2, 3, ...), as in the training plan.
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    # "kg" for weights; "min" for timed exercises like planks.
    unit: Mapped[str] = mapped_column(String(10), default="kg", server_default="kg")
    default_sets: Mapped[int] = mapped_column(default=3, server_default="3")
    # Machine setting, e.g. "Stufe 6". Shown in the briefing.
    gear_setting: Mapped[str | None] = mapped_column(Text)
    # Warnings, e.g. "Verletzung – je nach Tag".
    caution: Mapped[str | None] = mapped_column(Text)
    # Abbreviations the user types, e.g. ["BP", "Brust Presse"].
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    # Inactive = no longer in the plan, kept for history.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class TrainingSession(Base):
    """One workout on one day."""

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    focus: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entries: Mapped[list["TrainingEntry"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TrainingEntry.position",
    )


class TrainingEntry(Base):
    """One exercise within a session: weight × sets (no reps — same as the owner's Excel)."""

    __tablename__ = "training_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT: an exercise with history can't be deleted, only deactivated.
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int]
    # kg (or minutes for timed exercises); Numeric keeps 22.5 exact, read back as float.
    weight: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False))
    sets: Mapped[int]

    session: Mapped[TrainingSession] = relationship(back_populates="entries")
    exercise: Mapped[Exercise] = relationship()
