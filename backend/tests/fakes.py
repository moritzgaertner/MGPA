"""Test doubles shared by several test modules."""

import hashlib
import math
import re
from collections.abc import Sequence

from mgpa_backend.models import EMBEDDING_DIMENSIONS


class FakeEmbedder:
    """Deterministic bag-of-words embeddings: texts sharing words get similar vectors.

    Good enough to test ingestion and similarity search without calling Voyage.
    """

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []

    @staticmethod
    def vector(text: str) -> list[float]:
        values = [0.0] * EMBEDDING_DIMENSIONS
        for word in re.findall(r"\w+", text.lower()):
            bucket = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
            values[bucket % EMBEDDING_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [self.vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.vector(text)


class FailingEmbedder(FakeEmbedder):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("simulated Voyage outage")
