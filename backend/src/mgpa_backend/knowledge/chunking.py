"""Split a text into retrieval-sized chunks, keeping Markdown headings as context."""

import re
from dataclasses import dataclass

# Target maximum characters per chunk (~500 tokens): small enough to be specific in search,
# large enough to carry a complete thought.
MAX_CHUNK_CHARS = 2_000

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkDraft:
    index: int
    heading: str | None  # e.g. "Training › Day B"
    content: str


def chunk_text(text: str, *, markdown: bool, max_chars: int = MAX_CHUNK_CHARS) -> list[ChunkDraft]:
    """Chunk a document. Markdown is split along headings first, then by paragraphs."""
    sections = _markdown_sections(text) if markdown else [(None, text)]
    chunks: list[ChunkDraft] = []
    for heading, body in sections:
        for content in _pack_paragraphs(body, max_chars):
            chunks.append(ChunkDraft(index=len(chunks), heading=heading, content=content))
    return chunks


def _markdown_sections(text: str) -> list[tuple[str | None, str]]:
    """Group lines under their heading path. Headings inside ``` code blocks are ignored."""
    sections: list[tuple[str | None, str]] = []
    path: list[tuple[int, str]] = []  # (level, title) of the current heading and its parents
    lines: list[str] = []
    in_code = False

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            sections.append((" › ".join(title for _, title in path) or None, body))
        lines.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            path[:] = [(lvl, title) for lvl, title in path if lvl < level]
            path.append((level, match.group(2)))
        else:
            lines.append(line)
    flush()
    return sections


def _pack_paragraphs(body: str, max_chars: int) -> list[str]:
    """Join consecutive paragraphs into chunks of at most `max_chars` characters."""
    pieces = [
        piece
        for paragraph in re.split(r"\n\s*\n", body)
        if paragraph.strip()
        for piece in _split_long(paragraph.strip(), max_chars)
    ]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for piece in pieces:
        if current and size + len(piece) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(piece)
        size += len(piece) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    """Split an over-long paragraph at sentence ends; hard-cut sentences that are still too long."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    parts: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > max_chars:
            parts.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts
