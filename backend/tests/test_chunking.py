from mgpa_backend.knowledge.chunking import chunk_text

MARKDOWN = """\
# Training plan

Three-day split, once per week each.

## Day A

Chest press, incline dumbbell press.

## Day B

Leg press, Bulgarian split squats.

```python
# not a heading inside a code block
```
"""


def test_markdown_chunks_carry_their_heading_path() -> None:
    chunks = chunk_text(MARKDOWN, markdown=True)

    headings = [c.heading for c in chunks]
    assert headings == ["Training plan", "Training plan › Day A", "Training plan › Day B"]
    assert "Leg press" in chunks[2].content
    assert "# not a heading" in chunks[2].content  # code block stayed part of the section
    assert [c.index for c in chunks] == [0, 1, 2]


def test_plain_text_has_no_headings() -> None:
    chunks = chunk_text("# looks like a heading\n\nbut this is plain text", markdown=False)

    assert len(chunks) == 1
    assert chunks[0].heading is None


def test_long_text_is_split_below_the_limit() -> None:
    paragraph = " ".join(f"Sentence number {i} is here." for i in range(200))

    chunks = chunk_text(paragraph, markdown=False, max_chars=500)

    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    assert "Sentence number 199" in chunks[-1].content  # nothing lost at the end


def test_empty_text_gives_no_chunks() -> None:
    assert chunk_text("   \n\n  ", markdown=True) == []
