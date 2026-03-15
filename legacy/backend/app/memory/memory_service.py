"""High-level service for storing and retrieving musical memories.

``MemoryService`` ties together the embedding client, vector store, and
memory schemas to provide a clean async API consumed by the rest of the
application (primarily the live session flow in ``main.py``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .embeddings import EmbeddingClient
from .schemas import (
    MemorySearchResult,
    MemoryType,
    MusicalMemory,
    MusicalMemoryMetadata,
    SessionSummary,
)
from .vector_store import VectorStore

logger = logging.getLogger("eurydice.memory")

# Maximum characters shown per memory in the context preview.
_MAX_CONTENT_PREVIEW_LENGTH = 200


class MemoryService:
    """Orchestrates memory storage and retrieval for a music tutor."""

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.embeddings = embedding_client or EmbeddingClient()
        self.store = vector_store or VectorStore()

    # -- storage --------------------------------------------------------------

    async def store_memory(
        self,
        *,
        user_id: str,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MusicalMemory:
        """Embed *content* and persist it as a new memory."""
        embedding = await self.embeddings.embed_single(content)
        meta_kwargs = {k: v for k, v in (metadata or {}).items() if k in MusicalMemoryMetadata.model_fields}
        meta = MusicalMemoryMetadata(**meta_kwargs)
        memory = MusicalMemory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            metadata=meta,
        )
        self.store.add(memory)
        logger.debug("Stored %s memory for user %s (%d chars)", memory_type.value, user_id, len(content))
        return memory

    # -- retrieval ------------------------------------------------------------

    async def search_memories(
        self,
        *,
        query: str,
        user_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[MemorySearchResult]:
        """Embed *query* and return the most relevant memories."""
        query_embedding = await self.embeddings.embed_single(query)
        return self.store.search(
            query_embedding,
            user_id=user_id,
            memory_type=memory_type,
            top_k=top_k,
        )

    async def get_recent_memories(
        self,
        *,
        user_id: str,
        limit: int = 10,
    ) -> list[MusicalMemory]:
        """Return the most recent memories for a user."""
        return self.store.get_recent(user_id=user_id, limit=limit)

    # -- session summaries ----------------------------------------------------

    async def store_session_summary(
        self,
        *,
        session_id: str,
        user_id: str,
        summary: SessionSummary,
    ) -> MusicalMemory:
        """Embed and persist a structured session summary as a memory."""
        summary_text = self._format_summary_text(summary)
        meta_dict: dict[str, Any] = {
            "session_skill": summary.session_skill,
            "extra": {
                "session_id": session_id,
                "scales_practiced": summary.scales_practiced,
                "mistakes_detected": summary.mistakes_detected,
                "improvement_suggestions": summary.improvement_suggestions,
            },
        }
        if summary.overall_accuracy is not None:
            meta_dict["accuracy"] = summary.overall_accuracy
        return await self.store_memory(
            user_id=user_id,
            content=summary_text,
            memory_type=MemoryType.LESSON_SUMMARY,
            metadata=meta_dict,
        )

    # -- context building for prompts -----------------------------------------

    async def build_memory_context(
        self,
        *,
        query: str,
        user_id: str,
        top_k: int = 3,
        max_chars: int = 1200,
    ) -> str:
        """Build a compact memory context string for injection into prompts.

        Retrieves the most relevant memories and formats them as a
        bullet list that can be appended to the system prompt.
        """
        results = await self.search_memories(
            query=query,
            user_id=user_id,
            top_k=top_k,
        )
        if not results:
            return ""

        lines: list[str] = ["MUSICAL_MEMORIES:"]
        total_len = len(lines[0])
        for result in results:
            mem = result.memory
            content_preview = mem.content[:_MAX_CONTENT_PREVIEW_LENGTH].strip()
            if len(content_preview) >= _MAX_CONTENT_PREVIEW_LENGTH:
                content_preview = content_preview[:_MAX_CONTENT_PREVIEW_LENGTH - 3] + "..."
            line = (
                f"- [{mem.memory_type.value}] "
                f"(relevance={result.score:.2f}) "
                f"{content_preview}"
            )
            if total_len + len(line) + 1 > max_chars:
                break
            lines.append(line)
            total_len += len(line) + 1

        return "\n".join(lines) if len(lines) > 1 else ""

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _format_summary_text(summary: SessionSummary) -> str:
        """Convert a ``SessionSummary`` into embeddable prose."""
        parts: list[str] = []
        if summary.session_skill:
            parts.append(f"Session skill: {summary.session_skill}.")
        if summary.scales_practiced:
            parts.append(f"Scales practiced: {', '.join(summary.scales_practiced)}.")
        if summary.mistakes_detected:
            parts.append(f"Mistakes: {', '.join(summary.mistakes_detected)}.")
        if summary.improvement_suggestions:
            parts.append(f"Suggestions: {', '.join(summary.improvement_suggestions)}.")
        if summary.overall_accuracy is not None:
            parts.append(f"Overall accuracy: {round(summary.overall_accuracy * 100)}%.")
        if summary.raw_summary:
            parts.append(summary.raw_summary)
        return " ".join(parts) if parts else "Practice session completed."
