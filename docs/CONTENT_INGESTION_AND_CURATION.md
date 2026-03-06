# Eurydice Content Ingestion and Curation Workflow

This document defines how repertoire/exercise content enters Eurydice, how it is curated, and how it is loaded into guided lesson flow.

## Scope

Phase 5 content ecosystem adds three backend entities:

- `MusicLibraryItem`: canonical reusable content entry
- `MusicLessonPack`: ordered set of library items
- `MusicLessonPackEntry`: one item inside a pack with an expected outcome

## Content Model

Each `MusicLibraryItem` carries:

- `content_type`: `EXERCISE`, `REPERTOIRE`, `THEORY`, `ETUDE`, `LESSON_FRAGMENT`
- `instrument`: normalized to uppercase (for example `PIANO`, `GUITAR`, `VOICE`)
- `difficulty`: `BEGINNER`, `INTERMEDIATE`, `ADVANCED`
- `technique_tags`: normalized tags (for example `rhythm`, `intonation`, `timing`)
- `learning_objective`: short pedagogical target
- `source_format` + `source_text`: currently `NOTE_LINE` is loadable into guided flow
- `metadata`: extensible JSON map (for example `time_signature`)

## Ownership and Visibility

Two content classes are supported:

- User-generated content: visible to the creating user only
- Curated content: visible to all users

Curated creation is teacher-gated via:

- `VISTA_TEACHER_UID_ALLOWLIST`
- `VISTA_TEACHER_EMAIL_ALLOWLIST`

If `curated=true` is requested by a non-teacher, the API returns `403`.

## API Workflow

### 1) Ingest library items

`POST /api/music/library/items`

Use this endpoint to add reusable exercises/repertoire blocks with technique metadata.

### 2) Discover/filter items

`GET /api/music/library/items`

Supports filtering by:

- `instrument`
- `difficulty`
- `technique`
- `content_type`
- visibility control via `include_private`

### 3) Adaptive recommendation feed

`GET /api/music/library/recommendations/me`

Recommendation ranking reads `MusicSkillProfile.weakest_dimension` and prioritizes items by:

1. technique-tag alignment
2. curated visibility preference
3. difficulty sorting and recency

### 4) Build guided lesson packs

`POST /api/music/library/packs`

Creates an ordered pack from `item_ids` plus optional per-entry expected outcomes.

### 5) Load pack entry directly into guided lesson

`POST /api/music/library/packs/{pack_id}/load`

This endpoint imports the selected pack entry into the same guided workflow used by score preparation:

- creates a `MusicScore`
- prepares notation/render payload
- returns the first guided lesson step

## Curation Guidelines

- Keep each item focused on a single learning objective.
- Tag technique dimensions explicitly (`rhythm`, `timing`, `intonation`, `articulation`, `dynamics`) so adaptive ranking can work deterministically.
- Keep `source_text` short and atomic for pack composition (small reusable fragments).
- Use pack-level `expected_outcomes` for lesson-level goals and entry-level outcomes for bar/phrase goals.

## Current Constraints

- Pack loading into guided workflow currently supports `source_format=NOTE_LINE` only.
- MusicXML/MNX are supported at content schema level but not yet executable in `pack/load`.
- Recommendation logic is rules-based (deterministic) and designed to be extended by Phase 2 adaptive logic.

## Verification

Coverage exists in `backend/tests/test_music_transcription.py` for:

- filtering by instrument/difficulty/technique
- pack load into guided flow
- weakest-dimension recommendation behavior
