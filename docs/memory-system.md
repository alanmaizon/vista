# Musical Memory System

The memory subsystem gives the Eurydice AI tutor **persistent, personalised recall** across practice sessions. Instead of starting each session from scratch, the tutor remembers what the student practiced, where they struggled, and what was suggested — then uses that context to guide the next lesson.

## Architecture

```
backend/app/memory/
├── __init__.py          # Public API exports
├── schemas.py           # MusicalMemory, MemoryType, SessionSummary
├── embeddings.py        # Gemini embedding API wrapper
├── vector_store.py      # In-memory vector store with JSONL persistence
├── memory_service.py    # High-level store / search / context-building API
└── eval_memory.py       # Evaluation script
```

### Data Flow

```
User message or session end
        ↓
  EmbeddingClient.embed_single(text)
        ↓
  VectorStore.add(memory_with_embedding)
        ↓
  (persisted to memory_store.jsonl)

Next session start
        ↓
  MemoryService.build_memory_context(query, user_id)
        ↓
  EmbeddingClient.embed_single(query)
        ↓
  VectorStore.search(query_embedding, user_id)
        ↓
  Relevant memories injected into PromptComposer
        ↓
  Gemini Live receives personalised system prompt
```

## Memory Types

| Type | Description |
|------|-------------|
| `theory_explanation` | Musical theory the tutor explained |
| `practice_attempt` | A specific practice session or exercise |
| `correction_feedback` | Corrections given to the student |
| `lesson_summary` | End-of-session summary |
| `user_question` | Questions the student asked |
| `analysis_result` | Audio analysis outputs (pitch, rhythm) |

## Schema

Each memory record contains:

```json
{
  "id": "uuid-hex",
  "user_id": "firebase-uid",
  "timestamp": "2025-06-01T12:00:00Z",
  "memory_type": "practice_attempt",
  "content": "Practiced D minor scale at 90 BPM with 85% accuracy",
  "embedding": [0.12, -0.34, ...],
  "metadata": {
    "scale": "D minor",
    "tempo": 90,
    "accuracy": 0.85,
    "notes_played": ["D4", "E4", "F4"],
    "instrument": "piano",
    "session_skill": "GUIDED_LESSON"
  }
}
```

## Usage

### Storing a memory

```python
from app.memory import MemoryService, MemoryType

service = MemoryService()

await service.store_memory(
    user_id="user123",
    content="Practiced D minor scale at 90 BPM with 85% accuracy",
    memory_type=MemoryType.PRACTICE_ATTEMPT,
    metadata={"scale": "D minor", "tempo": 90, "accuracy": 0.85},
)
```

### Searching memories

```python
results = await service.search_memories(
    query="What scales should I practice today?",
    user_id="user123",
    top_k=5,
)

for result in results:
    print(f"{result.score:.2f} — {result.memory.content}")
```

### Building prompt context

```python
context = await service.build_memory_context(
    query="Let's work on scales",
    user_id="user123",
    top_k=3,
    max_chars=1200,
)
# Returns a formatted string like:
# MUSICAL_MEMORIES:
# - [practice_attempt] (relevance=0.92) Practiced D minor scale...
```

### Session summaries

```python
from app.memory import SessionSummary

summary = SessionSummary(
    session_id="session-uuid",
    user_id="user123",
    scales_practiced=["D minor", "G major"],
    mistakes_detected=["flat on F#", "rushing in bar 3"],
    improvement_suggestions=["Slow down descending passages"],
    overall_accuracy=0.82,
    session_skill="GUIDED_LESSON",
)

await service.store_session_summary(
    session_id="session-uuid",
    user_id="user123",
    summary=summary,
)
```

## Integration with Live Sessions

The memory system is integrated at two points in the live session lifecycle:

1. **Session start** — `_build_memory_context_for_user()` retrieves relevant memories and passes them to `PromptComposer`, which includes them in the Gemini system prompt.

2. **Session end** — `_store_session_memory_summary()` generates and stores a session summary as a memory for future recall.

3. **During conversation** — Substantive user text messages (>10 chars) are stored as `USER_QUESTION` memories.

## Evaluation

Run the evaluation script to verify retrieval accuracy, latency, and user isolation:

```bash
cd backend
python -m app.memory.eval_memory
```

Expected output:

```
  ✅ PASS  Retrieval accuracy
  ✅ PASS  Semantic ranking
  ✅ PASS  Cross-session recall
  ✅ PASS  Store latency
  ✅ PASS  Search latency
  ✅ PASS  User isolation
  6/6 evaluations passed
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MEMORY_STORE_PATH` | `memory_store.jsonl` | File path for persisting the vector store |

The embedding model defaults to `gemini-embedding-exp-03-07`. When the Gemini API is unavailable (e.g., in tests), the client gracefully degrades to zero vectors.

## Testing

```bash
cd backend
python -m pytest tests/test_memory.py -v
```

## Future Improvements

- **Managed vector database** — Replace the in-memory store with Chroma, Pinecone, or Cloud SQL pgvector for production scale.
- **Memory compaction** — Summarise and merge older memories to keep the context window efficient.
- **Selective embedding** — Use different embedding strategies for different memory types.
- **Memory decay** — Weight recent memories higher in retrieval scoring.
