"""In-process vector store backed by NumPy for musical memory retrieval.

This module provides a lightweight vector store that keeps embeddings
in memory and persists them to a JSON-lines file on disk.  It is designed
for single-process deployments (e.g. Cloud Run with one container) and
can be swapped out for a managed vector database (Chroma, Pinecone, etc.)
in the future without changing the ``MemoryService`` interface.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .schemas import MemorySearchResult, MusicalMemory

logger = logging.getLogger("eurydice.memory")

# Default file path for persisting the vector store.
_DEFAULT_STORE_PATH = os.getenv("MEMORY_STORE_PATH", "memory_store.jsonl")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class VectorStore:
    """Manages storage and retrieval of embedded musical memories.

    Memories are kept in an in-memory list and optionally flushed to a
    JSONL file so they survive process restarts.
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._memories: list[MusicalMemory] = []
        self._persist_path = persist_path
        self._lock = threading.Lock()
        if self._persist_path:
            self._load_from_disk()

    # -- persistence helpers --------------------------------------------------

    def _load_from_disk(self) -> None:
        """Load memories from the JSONL file if it exists."""
        path = Path(self._persist_path)  # type: ignore[arg-type]
        if not path.is_file():
            return
        loaded = 0
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._memories.append(MusicalMemory.model_validate_json(line))
                        loaded += 1
                    except Exception:
                        logger.debug("Skipping malformed memory line")
            logger.info("Loaded %d memories from %s", loaded, self._persist_path)
        except Exception as exc:
            logger.warning("Failed to load memory store from disk: %s", exc)

    def _append_to_disk(self, memory: MusicalMemory) -> None:
        """Append a single memory record to the JSONL file."""
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(memory.model_dump_json() + "\n")
        except Exception as exc:
            logger.warning("Failed to persist memory to disk: %s", exc)

    # -- public API -----------------------------------------------------------

    def add(self, memory: MusicalMemory) -> None:
        """Store a memory (with its embedding) in the index."""
        with self._lock:
            self._memories.append(memory)
            self._append_to_disk(memory)

    def search(
        self,
        query_embedding: list[float],
        *,
        user_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[MemorySearchResult]:
        """Return the *top_k* most similar memories to *query_embedding*.

        Optionally filter by ``user_id`` and/or ``memory_type`` before
        ranking.
        """
        query_vec = np.array(query_embedding, dtype=np.float32)
        candidates: list[tuple[float, MusicalMemory]] = []

        with self._lock:
            for mem in self._memories:
                if user_id and mem.user_id != user_id:
                    continue
                if memory_type and mem.memory_type.value != memory_type:
                    continue
                if mem.embedding is None:
                    continue
                mem_vec = np.array(mem.embedding, dtype=np.float32)
                score = _cosine_similarity(query_vec, mem_vec)
                candidates.append((score, mem))

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [
            MemorySearchResult(memory=mem, score=max(0.0, min(1.0, score)))
            for score, mem in candidates[: max(1, top_k)]
        ]

    def get_recent(
        self,
        *,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MusicalMemory]:
        """Return the most recent memories, optionally filtered by user."""
        with self._lock:
            filtered = [m for m in self._memories if not user_id or m.user_id == user_id]
        filtered.sort(key=lambda m: m.timestamp, reverse=True)
        return filtered[: max(1, limit)]

    def count(self, *, user_id: Optional[str] = None) -> int:
        """Return the total number of stored memories."""
        with self._lock:
            if user_id:
                return sum(1 for m in self._memories if m.user_id == user_id)
            return len(self._memories)

    def clear(self, *, user_id: Optional[str] = None) -> int:
        """Remove memories, optionally scoped to a user.  Returns count removed."""
        with self._lock:
            if user_id:
                before = len(self._memories)
                self._memories = [m for m in self._memories if m.user_id != user_id]
                return before - len(self._memories)
            removed = len(self._memories)
            self._memories.clear()
            return removed
