"""Wrapper around the Gemini embedding API for musical memory."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("eurydice.memory")

# Default embedding model from Google's Gemini family.
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-exp-03-07"

# Dimensionality produced by the default model (768 for gemini-embedding models).
DEFAULT_EMBEDDING_DIM = 768


class EmbeddingClient:
    """Thin wrapper around the ``google.genai`` embedding API.

    The client lazily initialises the underlying ``genai.Client`` on first
    use so that import-time side-effects are avoided (e.g. during testing).
    """

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model = model
        self._client: Optional[object] = None

    def _get_client(self) -> object:
        """Return (and lazily create) the ``genai.Client`` instance."""
        if self._client is None:
            try:
                from google import genai  # type: ignore[import-untyped]

                self._client = genai.Client()
            except Exception as exc:
                logger.warning("Failed to create genai.Client: %s", exc)
                raise
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text strings.

        Returns a list of float vectors, one per input text.
        Falls back to zero vectors when the API is unavailable so that
        offline / test environments degrade gracefully.
        """
        if not texts:
            return []
        try:
            client = self._get_client()
            result = client.models.embed_content(  # type: ignore[union-attr]
                model=self.model,
                contents=texts,
            )
            return [list(e.values) for e in result.embeddings]  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("Embedding API call failed, returning zero vectors: %s", exc)
            return [[0.0] * DEFAULT_EMBEDDING_DIM for _ in texts]

    async def embed_single(self, text: str) -> list[float]:
        """Convenience method to embed a single text string."""
        results = await self.embed([text])
        return results[0]
