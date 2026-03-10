"""Musical memory subsystem for Eurydice.

This package provides embedding-based storage and retrieval of musical
memories so the AI tutor can personalise guidance across sessions.

Quick start::

    from app.memory import MemoryService, MemoryType

    service = MemoryService()
    await service.store_memory(
        user_id="user123",
        content="Practiced D minor scale at 90 BPM with 85% accuracy",
        memory_type=MemoryType.PRACTICE_ATTEMPT,
        metadata={"scale": "D minor", "tempo": 90, "accuracy": 0.85},
    )

    results = await service.search_memories(
        query="What scales should I practice today?",
        user_id="user123",
    )
"""

from .embeddings import EmbeddingClient
from .memory_service import MemoryService
from .schemas import (
    MemorySearchResult,
    MemoryType,
    MusicalMemory,
    MusicalMemoryMetadata,
    SessionSummary,
)
from .vector_store import VectorStore

__all__ = [
    "EmbeddingClient",
    "MemorySearchResult",
    "MemoryService",
    "MemoryType",
    "MusicalMemory",
    "MusicalMemoryMetadata",
    "SessionSummary",
    "VectorStore",
]
