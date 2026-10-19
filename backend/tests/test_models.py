"""Model tests against the real (migrated) Postgres. Each test is rolled back afterwards."""

from collections.abc import Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mgpa_backend.db import engine
from mgpa_backend.models import Conversation, Message, MessageRole


@pytest.fixture
def db() -> Iterator[Session]:
    """A session inside a transaction that is always rolled back, so tests leave no data."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


def test_conversation_with_messages_roundtrip(db: Session) -> None:
    conversation = Conversation(
        messages=[
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi! How can I help?"),
        ]
    )
    db.add(conversation)
    db.commit()
    db.expire_all()  # force a fresh load from the database

    loaded = db.get_one(Conversation, conversation.id)
    assert [m.content for m in loaded.messages] == ["Hello", "Hi! How can I help?"]
    assert loaded.created_at is not None  # set by the database
    assert loaded.title is None


def test_role_is_stored_as_lowercase_value(db: Session) -> None:
    db.add(Conversation(messages=[Message(role=MessageRole.USER, content="x")]))
    db.commit()

    stored = db.execute(text("SELECT role::text FROM messages")).scalar_one()
    assert stored == "user"


def test_deleting_conversation_deletes_its_messages(db: Session) -> None:
    conversation = Conversation(messages=[Message(role=MessageRole.USER, content="x")])
    db.add(conversation)
    db.commit()

    db.delete(conversation)
    db.commit()

    assert db.scalars(select(Message)).all() == []


def test_message_requires_existing_conversation(db: Session) -> None:
    db.add(Message(conversation_id=999_999, role=MessageRole.USER, content="orphan"))

    with pytest.raises(IntegrityError):
        db.commit()
