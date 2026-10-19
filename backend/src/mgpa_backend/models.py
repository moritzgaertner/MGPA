"""ORM models: every class here becomes one table in Postgres."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mgpa_backend.db import Base


class MessageRole(StrEnum):
    """Who wrote a message. Stored as a Postgres enum, so typos are rejected."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    """One chat thread."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Empty at first; a title can be generated from the first message later.
    title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Bumped whenever the row is updated; the chat endpoint touches it on every new message.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        # Deleting a conversation deletes its messages; the database does it (passive_deletes).
        cascade="all, delete-orphan",
        passive_deletes=True,
        # Order by id, not created_at: messages saved in one transaction share the same now().
        order_by="Message.id",
    )


class Message(Base):
    """One message inside a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # values_callable: store the values ("user"), not the member names ("USER")
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", values_callable=lambda e: [m.value for m in e])
    )
    # Chat messages can be arbitrarily long, so Text instead of String(n).
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
