"""ORM models: every class here becomes one table in Postgres.

=============================================================================
HOW A MODEL LOOKS — example from a different domain (authors and books).
Do NOT copy it 1:1 — transfer the pattern to conversations and messages.
=============================================================================

    class Author(Base):
        __tablename__ = "authors"                       # table name in Postgres

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(200))   # NOT NULL (no `| None`)
        bio: Mapped[str | None] = mapped_column(Text)    # nullable because of `| None`
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), server_default=func.now()
        )

        # Python-side shortcut: author.books -> list of Book objects (no extra column!)
        books: Mapped[list["Book"]] = relationship(
            back_populates="author", cascade="all, delete-orphan"
        )


    class Book(Base):
        __tablename__ = "books"

        id: Mapped[int] = mapped_column(primary_key=True)
        # The real column: which author does this book belong to?
        author_id: Mapped[int] = mapped_column(
            ForeignKey("authors.id", ondelete="CASCADE"), index=True
        )
        title: Mapped[str] = mapped_column(String(300))

        # The other side of the shortcut: book.author -> Author object
        author: Mapped["Author"] = relationship(back_populates="books")

Imports you will need (add them at the top, ruff tells you if one is unused):
    from datetime import datetime
    from enum import StrEnum
    from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
    from sqlalchemy.orm import Mapped, mapped_column, relationship
    from mgpa_backend.db import Base

Docs: https://docs.sqlalchemy.org/en/21/orm/quickstart.html
      https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-many
"""

# TODO 1 — MessageRole
#   A Python enum (class MessageRole(StrEnum)) with the two possible senders of a message:
#   the user and the assistant. Values are lowercase strings, e.g. "user".
#   Why an enum instead of a plain string? Think about what happens with a typo like "assitant".
#   In the column, use: mapped_column(Enum(MessageRole, name="message_role"))


# TODO 2 — Conversation  (table "conversations")
#   One chat thread. Columns to think about:
#   - id            primary key
#   - title         short text, may be empty at first (the title can be generated later)
#   - created_at    when the conversation started (let the DATABASE set it: server_default)
#   - updated_at    when the last message arrived — hint: mapped_column(..., onupdate=func.now())
#   Plus the relationship `messages` (list of Message).
#   Question for you: if a conversation is deleted, what should happen to its messages?
#   Hint: should the messages come back ordered? Look up `order_by` on relationship().


# TODO 3 — Message  (table "messages")
#   One single message inside a conversation. Columns to think about:
#   - id                primary key
#   - conversation_id   foreign key to conversations.id — what should ondelete be?
#                       index=True: we will often query "all messages of conversation X"
#   - role              MessageRole (who wrote it)
#   - content           the message text — can be long, so String(n) or Text?
#   - created_at        set by the database
#   Plus the relationship `conversation` back to Conversation.


# CHECK when you are done (from the backend/ folder, with the database running):
#   uv run ruff check . && uv run ruff format . && uv run mypy src tests
#   uv run python -c "from mgpa_backend.models import Conversation, Message; print('ok')"
