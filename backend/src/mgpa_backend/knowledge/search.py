"""Semantic search over the knowledge base (cosine similarity in pgvector)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from mgpa_backend.models import Chunk, Document, DocumentStatus

# Below this similarity a chunk is considered unrelated and not shown to Claude.
MIN_SIMILARITY = 0.3


@dataclass(frozen=True)
class SearchHit:
    document_id: int
    filename: str
    heading: str | None
    content: str
    similarity: float  # 1.0 = same meaning, 0 = unrelated

    @property
    def source(self) -> str:
        """Citation label, e.g. "plan.md › Day B"."""
        return self.filename if self.heading is None else f"{self.filename} › {self.heading}"


def search_chunks(db: Session, query_embedding: list[float], limit: int = 5) -> list[SearchHit]:
    """The `limit` chunks closest in meaning to the query, from ready documents only."""
    distance = Chunk.embedding.cosine_distance(query_embedding)
    rows = db.execute(
        select(Chunk, Document.filename, distance.label("distance"))
        .join(Document)
        .where(Document.status == DocumentStatus.READY)
        .order_by(distance)
        .limit(limit)
    ).all()
    hits = [
        SearchHit(
            document_id=chunk.document_id,
            filename=filename,
            heading=chunk.heading,
            content=chunk.content,
            similarity=1 - float(dist),
        )
        for chunk, filename, dist in rows
    ]
    return [hit for hit in hits if hit.similarity >= MIN_SIMILARITY]
