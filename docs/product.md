# Product

## Working concept

An Ancient Greek tutor that can hear the learner, inspect a passage or worksheet, and respond in real time with spoken coaching, guided parsing, and translation hints.

## Core experience

- The learner enters a short target passage or uploads a worksheet image.
- The learner speaks aloud or asks a question.
- The tutor responds with short live guidance rather than long written explanations.
- The tutor can surface morphology cues, translation nudges, or a follow-up drill.

## Tutor modes in the scaffold

- `guided_reading`: support oral reading and keep the learner oriented in the clause.
- `morphology_coach`: focus on endings, forms, and syntactic role.
- `translation_support`: help the learner arrive at a translation step by step.
- `oral_reading`: emphasize pronunciation, pacing, and chunking.

## Product principles

- Voice first, not chat first
- Use the visible text before guessing
- Prefer hints and guided discovery over immediate answers
- Keep feedback concise enough for a live spoken loop

## Non-goals for this scaffold

- full tutoring intelligence
- curriculum management
- authentication
- persistent learner memory
- final production infrastructure

## Near-term build steps

1. Land a real Gemini Live transport layer.
2. Add ADK policy evaluation coverage to validate tool routing decisions across modes.
3. Implement the first richer parser response shape so the UI can render meaningful morphology cards.
4. Add turn logging and session playback for debugging.
