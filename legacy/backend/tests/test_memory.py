"""Tests for the musical memory subsystem.

Covers schemas, vector store, memory service, and prompt integration.
All tests run without network access by mocking the embedding client.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

import numpy as np
import pytest

from app.memory.schemas import (
    MemorySearchResult,
    MemoryType,
    MusicalMemory,
    MusicalMemoryMetadata,
    SessionSummary,
)
from app.memory.vector_store import VectorStore, _cosine_similarity
from app.memory.memory_service import MemoryService
from app.memory.embeddings import EmbeddingClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding(dim: int = 768, seed: int = 0) -> list[float]:
    """Generate a deterministic random unit vector."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


class FakeEmbeddingClient(EmbeddingClient):
    """Deterministic embedding client for testing.

    Maps known phrases to pre-defined directions so that semantic
    similarity tests are reproducible.
    """

    _PHRASE_SEEDS = {
        "D minor scale": 1,
        "C major scale": 2,
        "practice session": 3,
        "What should I practice today?": 1,  # same direction as D minor
        "rhythm exercise": 4,
        "intonation feedback": 5,
    }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            seed = self._PHRASE_SEEDS.get(text, hash(text) % 10000)
            results.append(_make_embedding(seed=seed))
        return results

    async def embed_single(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_musical_memory_defaults(self) -> None:
        mem = MusicalMemory(
            user_id="u1",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
            content="Practiced C major",
        )
        assert mem.user_id == "u1"
        assert mem.memory_type == MemoryType.PRACTICE_ATTEMPT
        assert mem.embedding is None
        assert isinstance(mem.id, str)
        assert len(mem.id) == 32  # uuid4 hex

    def test_memory_type_enum_values(self) -> None:
        assert MemoryType.THEORY_EXPLANATION.value == "theory_explanation"
        assert MemoryType.LESSON_SUMMARY.value == "lesson_summary"
        assert MemoryType.USER_QUESTION.value == "user_question"

    def test_session_summary_defaults(self) -> None:
        summary = SessionSummary(session_id="s1", user_id="u1")
        assert summary.scales_practiced == []
        assert summary.overall_accuracy is None

    def test_memory_metadata_extra_fields(self) -> None:
        meta = MusicalMemoryMetadata(
            scale="D minor", tempo=120.0, extra={"custom": True}
        )
        assert meta.scale == "D minor"
        assert meta.extra["custom"] is True

    def test_memory_search_result_score_clamped(self) -> None:
        mem = MusicalMemory(
            user_id="u1",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
            content="test",
        )
        result = MemorySearchResult(memory=mem, score=0.95)
        assert result.score == 0.95


# ---------------------------------------------------------------------------
# Vector store tests
# ---------------------------------------------------------------------------


class TestVectorStore:
    def test_add_and_count(self) -> None:
        store = VectorStore()
        mem = MusicalMemory(
            user_id="u1",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
            content="Practiced D minor scale",
            embedding=_make_embedding(seed=1),
        )
        store.add(mem)
        assert store.count() == 1
        assert store.count(user_id="u1") == 1
        assert store.count(user_id="u2") == 0

    def test_search_returns_most_similar(self) -> None:
        store = VectorStore()
        # Add two memories with different embeddings.
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="D minor scale practice",
                embedding=_make_embedding(seed=1),
            )
        )
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.THEORY_EXPLANATION,
                content="C major theory",
                embedding=_make_embedding(seed=2),
            )
        )
        # Query with the same direction as seed=1 should rank D minor first.
        results = store.search(_make_embedding(seed=1), user_id="u1", top_k=2)
        assert len(results) == 2
        assert results[0].memory.content == "D minor scale practice"
        assert results[0].score > results[1].score

    def test_search_filters_by_user(self) -> None:
        store = VectorStore()
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="User 1 memory",
                embedding=_make_embedding(seed=1),
            )
        )
        store.add(
            MusicalMemory(
                user_id="u2",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="User 2 memory",
                embedding=_make_embedding(seed=2),
            )
        )
        results = store.search(_make_embedding(seed=1), user_id="u1", top_k=5)
        assert all(r.memory.user_id == "u1" for r in results)

    def test_search_filters_by_memory_type(self) -> None:
        store = VectorStore()
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="Practice",
                embedding=_make_embedding(seed=1),
            )
        )
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.THEORY_EXPLANATION,
                content="Theory",
                embedding=_make_embedding(seed=2),
            )
        )
        results = store.search(
            _make_embedding(seed=1),
            memory_type="theory_explanation",
            top_k=5,
        )
        assert len(results) == 1
        assert results[0].memory.memory_type == MemoryType.THEORY_EXPLANATION

    def test_get_recent_ordering(self) -> None:
        store = VectorStore()
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="Older",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        )
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="Newer",
                timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
            )
        )
        recent = store.get_recent(user_id="u1", limit=1)
        assert len(recent) == 1
        assert recent[0].content == "Newer"

    def test_clear_user_scoped(self) -> None:
        store = VectorStore()
        store.add(
            MusicalMemory(
                user_id="u1",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="u1 mem",
                embedding=_make_embedding(seed=1),
            )
        )
        store.add(
            MusicalMemory(
                user_id="u2",
                memory_type=MemoryType.PRACTICE_ATTEMPT,
                content="u2 mem",
                embedding=_make_embedding(seed=2),
            )
        )
        removed = store.clear(user_id="u1")
        assert removed == 1
        assert store.count() == 1
        assert store.count(user_id="u2") == 1

    def test_persistence_round_trip(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            store1 = VectorStore(persist_path=path)
            store1.add(
                MusicalMemory(
                    user_id="u1",
                    memory_type=MemoryType.PRACTICE_ATTEMPT,
                    content="Persisted memory",
                    embedding=_make_embedding(seed=1),
                )
            )
            assert store1.count() == 1

            # New store instance should load from disk.
            store2 = VectorStore(persist_path=path)
            assert store2.count() == 1
            assert store2.get_recent(user_id="u1")[0].content == "Persisted memory"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Cosine similarity edge cases
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        vec = _make_embedding(seed=42)
        assert abs(_cosine_similarity(np.array(vec), np.array(vec)) - 1.0) < 1e-5

    def test_orthogonal_vectors(self) -> None:
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert abs(_cosine_similarity(a, b)) < 1e-5

    def test_zero_vector(self) -> None:
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert _cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# Memory service tests
# ---------------------------------------------------------------------------


class TestMemoryService:
    @pytest.fixture()
    def service(self) -> MemoryService:
        return MemoryService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=VectorStore(),
        )

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, service: MemoryService) -> None:
        await service.store_memory(
            user_id="u1",
            content="D minor scale",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
            metadata={"scale": "D minor"},
        )
        results = await service.search_memories(
            query="D minor scale",
            user_id="u1",
        )
        assert len(results) >= 1
        assert results[0].memory.content == "D minor scale"
        assert results[0].score > 0.9  # should be near 1.0 for identical text

    @pytest.mark.asyncio
    async def test_semantic_similarity_ranking(self, service: MemoryService) -> None:
        """Query for 'D minor' should rank D minor memory above C major."""
        await service.store_memory(
            user_id="u1",
            content="D minor scale",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
        )
        await service.store_memory(
            user_id="u1",
            content="rhythm exercise",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
        )
        results = await service.search_memories(
            query="What should I practice today?",
            user_id="u1",
            top_k=2,
        )
        # 'What should I practice today?' maps to same seed as 'D minor scale'
        assert results[0].memory.content == "D minor scale"

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, service: MemoryService) -> None:
        await service.store_memory(
            user_id="u1",
            content="First session",
            memory_type=MemoryType.LESSON_SUMMARY,
        )
        await service.store_memory(
            user_id="u1",
            content="Second session",
            memory_type=MemoryType.LESSON_SUMMARY,
        )
        recent = await service.get_recent_memories(user_id="u1", limit=1)
        assert len(recent) == 1
        assert recent[0].content == "Second session"

    @pytest.mark.asyncio
    async def test_store_session_summary(self, service: MemoryService) -> None:
        summary = SessionSummary(
            session_id="s1",
            user_id="u1",
            scales_practiced=["D minor", "G major"],
            mistakes_detected=["flat on F#"],
            improvement_suggestions=["Practice slowly"],
            overall_accuracy=0.82,
            session_skill="GUIDED_LESSON",
        )
        mem = await service.store_session_summary(
            session_id="s1",
            user_id="u1",
            summary=summary,
        )
        assert mem.memory_type == MemoryType.LESSON_SUMMARY
        assert "D minor" in mem.content
        assert "flat on F#" in mem.content
        assert mem.metadata.accuracy == 0.82

    @pytest.mark.asyncio
    async def test_build_memory_context(self, service: MemoryService) -> None:
        await service.store_memory(
            user_id="u1",
            content="D minor scale",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
        )
        ctx = await service.build_memory_context(
            query="D minor scale",
            user_id="u1",
        )
        assert "MUSICAL_MEMORIES:" in ctx
        assert "D minor scale" in ctx

    @pytest.mark.asyncio
    async def test_build_memory_context_empty(self, service: MemoryService) -> None:
        ctx = await service.build_memory_context(
            query="anything",
            user_id="u1",
        )
        # No memories stored → empty string
        assert ctx == ""

    @pytest.mark.asyncio
    async def test_cross_session_recall(self, service: MemoryService) -> None:
        """Simulate multi-session recall: store in session 1, retrieve in session 2."""
        # Session 1: user practices D minor
        await service.store_memory(
            user_id="u1",
            content="D minor scale",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
            metadata={"scale": "D minor", "tempo": 80, "accuracy": 0.75},
        )
        await service.store_session_summary(
            session_id="s1",
            user_id="u1",
            summary=SessionSummary(
                session_id="s1",
                user_id="u1",
                scales_practiced=["D minor"],
                mistakes_detected=["Intonation on F"],
                improvement_suggestions=["Slow down on descending passage"],
                overall_accuracy=0.75,
                session_skill="GUIDED_LESSON",
            ),
        )

        # Session 2: user asks what to practice
        results = await service.search_memories(
            query="What should I practice today?",
            user_id="u1",
            top_k=3,
        )
        assert len(results) >= 1
        # The D minor practice memory should be recalled.
        contents = [r.memory.content for r in results]
        assert any("D minor" in c for c in contents)


# ---------------------------------------------------------------------------
# Prompt composer integration
# ---------------------------------------------------------------------------


class TestPromptComposerMemoryIntegration:
    """Verify PromptComposer correctly includes memory context."""

    def test_prompt_includes_memory_context(self) -> None:
        pytest.importorskip("fastapi")
        from app.prompts import PromptComposer
        from app.domains.music.runtime import MusicRuntime

        runtime = MusicRuntime(skill="HEAR_PHRASE", goal="Identify this phrase")
        composer = PromptComposer(
            runtime,
            live_context="PROFILE: pitch=80%",
            memory_context="MUSICAL_MEMORIES:\n- [practice_attempt] D minor scale",
        )
        prompt = composer.get_system_prompt()
        assert "MUSICAL_MEMORIES:" in prompt
        assert "D minor scale" in prompt
        assert "PROFILE: pitch=80%" in prompt

    def test_prompt_without_memory_context(self) -> None:
        pytest.importorskip("fastapi")
        from app.prompts import PromptComposer
        from app.domains.music.runtime import MusicRuntime

        runtime = MusicRuntime(skill="HEAR_PHRASE", goal="Identify this phrase")
        composer = PromptComposer(runtime, live_context="", memory_context="")
        prompt = composer.get_system_prompt()
        assert "MUSICAL_MEMORIES:" not in prompt
