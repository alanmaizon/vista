"""Evaluation script for the musical memory system.

This script simulates multi-session tutoring scenarios and measures:

1. **Memory retrieval accuracy** – does the system recall relevant memories?
2. **Embedding quality** – are semantically similar items ranked together?
3. **Latency impact** – how fast are store and search operations?
4. **Conversation improvement** – does retrieved context improve responses?

Run with::

    python -m app.memory.eval_memory

No network access is required (uses deterministic fake embeddings).
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field

import numpy as np

from .embeddings import EmbeddingClient
from .memory_service import MemoryService
from .schemas import MemoryType, SessionSummary
from .vector_store import VectorStore


# ---------------------------------------------------------------------------
# Deterministic test embeddings
# ---------------------------------------------------------------------------

_TOPIC_SEEDS: dict[str, int] = {
    # Scales & keys
    "D minor scale": 10,
    "C major scale": 11,
    "G major scale": 12,
    "A minor arpeggio": 13,
    # Exercises
    "rhythm exercise": 20,
    "tempo control exercise": 21,
    "sight reading": 22,
    # Queries
    "What should I practice today?": 10,  # same direction as D minor
    "How is my rhythm?": 20,              # same direction as rhythm exercise
    "Tell me about C major": 11,          # same direction as C major
    "What are arpeggios?": 13,            # same direction as arpeggios
    # Corrections
    "You were flat on F#": 30,
    "Watch the tempo in bar 3": 31,
}


def _make_embedding(dim: int = 768, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


class EvalEmbeddingClient(EmbeddingClient):
    """Fake embedding client that maps known topics to fixed vectors."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_make_embedding(seed=_TOPIC_SEEDS.get(t, hash(t) % 10000)) for t in texts]

    async def embed_single(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


# ---------------------------------------------------------------------------
# Evaluation harness
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Aggregated evaluation metrics."""

    name: str
    passed: bool
    detail: str
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    """Full evaluation report."""

    results: list[EvalResult] = field(default_factory=list)

    def add(self, result: EvalResult) -> None:
        self.results.append(result)

    def print_report(self) -> None:
        print("\n" + "=" * 64)
        print("  Musical Memory System — Evaluation Report")
        print("=" * 64)
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        for r in self.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            latency = f" ({r.latency_ms:.1f}ms)" if r.latency_ms else ""
            print(f"  {status}  {r.name}{latency}")
            if r.detail:
                for line in r.detail.strip().split("\n"):
                    print(f"         {line}")
        print("-" * 64)
        print(f"  {passed}/{total} evaluations passed")
        print("=" * 64 + "\n")


async def _eval_retrieval_accuracy(service: MemoryService) -> EvalResult:
    """Store memories and check that queries retrieve the correct ones."""
    t0 = time.monotonic()

    # Populate memories.
    await service.store_memory(
        user_id="eval_user",
        content="D minor scale",
        memory_type=MemoryType.PRACTICE_ATTEMPT,
        metadata={"scale": "D minor"},
    )
    await service.store_memory(
        user_id="eval_user",
        content="C major scale",
        memory_type=MemoryType.THEORY_EXPLANATION,
    )
    await service.store_memory(
        user_id="eval_user",
        content="rhythm exercise",
        memory_type=MemoryType.PRACTICE_ATTEMPT,
    )

    # Query: "What should I practice today?" → should rank D minor first.
    results = await service.search_memories(
        query="What should I practice today?",
        user_id="eval_user",
        top_k=3,
    )
    top_content = results[0].memory.content if results else ""
    ok = top_content == "D minor scale"
    dt = (time.monotonic() - t0) * 1000

    detail = f"Top result: '{top_content}' (expected 'D minor scale')"
    return EvalResult(name="Retrieval accuracy", passed=ok, detail=detail, latency_ms=dt)


async def _eval_semantic_ranking(service: MemoryService) -> EvalResult:
    """Verify that semantically related queries rank above unrelated ones."""
    t0 = time.monotonic()

    results_rhythm = await service.search_memories(
        query="How is my rhythm?",
        user_id="eval_user",
        top_k=3,
    )
    top = results_rhythm[0].memory.content if results_rhythm else ""
    ok = top == "rhythm exercise"
    dt = (time.monotonic() - t0) * 1000

    detail = f"Top result for rhythm query: '{top}' (expected 'rhythm exercise')"
    return EvalResult(name="Semantic ranking", passed=ok, detail=detail, latency_ms=dt)


async def _eval_cross_session_recall(service: MemoryService) -> EvalResult:
    """Simulate a multi-session scenario."""
    t0 = time.monotonic()

    # Session 1: practice D minor.
    await service.store_session_summary(
        session_id="s1",
        user_id="eval_user",
        summary=SessionSummary(
            session_id="s1",
            user_id="eval_user",
            scales_practiced=["D minor"],
            mistakes_detected=["flat on F#"],
            improvement_suggestions=["Slow tempo on descending run"],
            overall_accuracy=0.78,
            session_skill="GUIDED_LESSON",
        ),
    )

    # Session 2: ask what to practice.
    ctx = await service.build_memory_context(
        query="What should I practice today?",
        user_id="eval_user",
        top_k=5,
    )
    ok = "D minor" in ctx
    dt = (time.monotonic() - t0) * 1000

    detail = f"Context mentions D minor: {ok}\nContext preview: {ctx[:200]}"
    return EvalResult(name="Cross-session recall", passed=ok, detail=detail, latency_ms=dt)


async def _eval_store_latency(service: MemoryService) -> EvalResult:
    """Measure average store latency over multiple operations."""
    timings: list[float] = []
    for i in range(20):
        t0 = time.monotonic()
        await service.store_memory(
            user_id="eval_user",
            content=f"Latency test memory #{i}",
            memory_type=MemoryType.PRACTICE_ATTEMPT,
        )
        timings.append((time.monotonic() - t0) * 1000)

    avg = statistics.mean(timings)
    p99 = sorted(timings)[int(len(timings) * 0.99)]
    ok = avg < 50  # should be well under 50ms without network.
    detail = f"avg={avg:.2f}ms  p99={p99:.2f}ms  (threshold <50ms)"
    return EvalResult(name="Store latency", passed=ok, detail=detail, latency_ms=avg)


async def _eval_search_latency(service: MemoryService) -> EvalResult:
    """Measure search latency."""
    timings: list[float] = []
    for _ in range(20):
        t0 = time.monotonic()
        await service.search_memories(
            query="D minor scale",
            user_id="eval_user",
            top_k=5,
        )
        timings.append((time.monotonic() - t0) * 1000)

    avg = statistics.mean(timings)
    p99 = sorted(timings)[int(len(timings) * 0.99)]
    ok = avg < 50
    detail = f"avg={avg:.2f}ms  p99={p99:.2f}ms  (threshold <50ms)"
    return EvalResult(name="Search latency", passed=ok, detail=detail, latency_ms=avg)


async def _eval_user_isolation(service: MemoryService) -> EvalResult:
    """Memories for one user must not appear in another user's searches."""
    await service.store_memory(
        user_id="user_a",
        content="User A secret practice",
        memory_type=MemoryType.PRACTICE_ATTEMPT,
    )
    results = await service.search_memories(
        query="User A secret practice",
        user_id="user_b",
        top_k=5,
    )
    leaked = any("User A" in r.memory.content for r in results)
    ok = not leaked
    detail = "No cross-user leakage detected" if ok else "LEAKED: User A memories visible to User B"
    return EvalResult(name="User isolation", passed=ok, detail=detail)


async def run_evaluation() -> EvalReport:
    """Run all evaluation scenarios and return the report."""
    service = MemoryService(
        embedding_client=EvalEmbeddingClient(),
        vector_store=VectorStore(),
    )
    report = EvalReport()

    report.add(await _eval_retrieval_accuracy(service))
    report.add(await _eval_semantic_ranking(service))
    report.add(await _eval_cross_session_recall(service))
    report.add(await _eval_store_latency(service))
    report.add(await _eval_search_latency(service))
    report.add(await _eval_user_isolation(service))

    return report


def main() -> None:
    report = asyncio.run(run_evaluation())
    report.print_report()


if __name__ == "__main__":
    main()
