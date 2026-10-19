"""Model tests against the real (migrated) Postgres. Each test is rolled back afterwards."""

from collections.abc import Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mgpa_backend.db import engine
from mgpa_backend.models import (
    Conversation,
    Document,
    DocumentStatus,
    Message,
    MessageRole,
    Task,
)


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


def test_new_task_is_open(db: Session) -> None:
    task = Task(title="Send application")
    db.add(task)
    db.commit()

    assert task.is_done is False
    assert task.due_date is None


def test_defaults_also_apply_to_rows_inserted_with_plain_sql(db: Session) -> None:
    # Simulates another process (e.g. Dagster or a manual SQL fix) that bypasses the ORM.
    db.execute(
        text(
            "INSERT INTO documents (filename, media_type, size_bytes, sha256, storage_path) "
            "VALUES ('cv.pdf', 'application/pdf', 1234, :sha, 'uploads/cv.pdf')"
        ),
        {"sha": "a" * 64},
    )
    db.execute(text("INSERT INTO tasks (title) VALUES ('Raw SQL task')"))

    document = db.scalars(select(Document)).one()
    task = db.scalars(select(Task)).one()
    assert document.status == DocumentStatus.PENDING
    assert document.created_at is not None
    assert task.is_done is False


def test_same_file_cannot_be_uploaded_twice(db: Session) -> None:
    for _ in range(2):
        db.add(
            Document(
                filename="cv.pdf",
                media_type="application/pdf",
                size_bytes=1234,
                sha256="b" * 64,
                storage_path="uploads/cv.pdf",
            )
        )

    with pytest.raises(IntegrityError):
        db.commit()
