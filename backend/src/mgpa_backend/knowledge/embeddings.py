"""Turn text into vectors with Voyage AI. Behind a small interface so tests can use a fake."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from voyageai.client import Client as VoyageClient

from mgpa_backend.config import get_settings
from mgpa_backend.models import EMBEDDING_DIMENSIONS

# Texts per API request (Voyage allows up to 1,000; smaller batches keep requests modest).
BATCH_SIZE = 64


class Embedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingsNotConfiguredError(RuntimeError):
    """Raised when the knowledge base is used without a VOYAGE_API_KEY."""


class VoyageEmbedder:
    """Voyage embeddings. Documents and queries are embedded differently (`input_type`),
    which Voyage recommends for retrieval quality."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = VoyageClient(api_key=api_key, max_retries=3, timeout=60)
        self._model = model

    def _embed(self, texts: Sequence[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            result = self._client.embed(
                list(texts[start : start + BATCH_SIZE]),
                model=self._model,
                input_type=input_type,
                output_dimension=EMBEDDING_DIMENSIONS,
            )
            vectors.extend([float(x) for x in vector] for vector in result.embeddings)
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.voyage_api_key is None:
        raise EmbeddingsNotConfiguredError("VOYAGE_API_KEY is not set, the knowledge base is off")
    return VoyageEmbedder(settings.voyage_api_key.get_secret_value(), settings.embedding_model)
