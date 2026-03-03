# Eurydice Challenge Brief

## One-Line Pitch

Eurydice is a real-time music tutor that can hear a student play, read their score, coach them bar by bar in voice, and adapt the lesson live until the phrase is learned.

## Elevator Pitch

Most music-learning tools solve only one slice of the journey: they either scan notation, listen for note accuracy, or provide static lessons. Eurydice combines those pieces into one multimodal agent. A learner can ask for help with a song, provide a score or tab, receive a guided lesson plan, practice one bar at a time, get immediate performance feedback, and continue until the full passage is playable with confidence.

## Challenge Positioning

Eurydice is the primary challenge project for this repo. Janey Mac was the first domain concept, but the repo itself is being built during the Gemini Live Agent Challenge period and the submission should present Eurydice as a distinct new product.

This project fits the **Live Agents** category directly:

- It uses real-time voice interaction.
- It uses camera input for score framing and reading.
- It provides step-by-step live tutoring.
- It is an agent, not a static classifier or offline utility.

## Problem Statement

Learning a song usually breaks across too many disconnected tools:

- a score viewer or tab site
- a tuner or pitch app
- a lesson video
- a separate metronome or looper
- manual self-evaluation

That fragmentation causes drop-off, confusion, and weak feedback loops. A student often does not know:

- what to practice first
- whether they played the right notes
- whether the rhythm was close enough
- whether the next step is to slow down, repeat, isolate, or move on

Eurydice’s job is to unify that loop.

## Product Thesis

Eurydice should be a **start-to-finish music guidance agent**:

1. It understands the learner’s intent.
2. It ingests a score, tab, or played phrase.
3. It plans a lesson at the right difficulty.
4. It guides one unit at a time (bar, phrase, interval, arpeggio).
5. It listens to the user perform.
6. It compares actual vs intended output.
7. It gives concise, corrective feedback.
8. It recommends the next best exercise.

The product is not just “pitch detection” and not just “sheet music scanning.” It is a **closed-loop tutor**.

## Main Workflow

### Core Guided Lesson Flow

1. User says: “Help me learn this song.”
2. Eurydice asks:
   - instrument
   - skill level
   - whether the goal is melody, chords, rhythm, or full passage
3. User provides:
   - score image
   - score line / symbolic notation
   - or a short played reference
4. Eurydice normalizes the target into symbolic form.
5. Eurydice selects the next practice unit:
   - one bar
   - one phrase
   - one chord change
   - one arpeggio shape
6. User plays.
7. Eurydice transcribes and compares.
8. Eurydice responds:
   - what was correct
   - what was wrong
   - whether to replay
   - whether to move on
9. Eurydice loops until the unit passes confidence and accuracy thresholds.
10. Eurydice advances and summarizes progress.

### Fast “Hear Phrase” Flow

1. User selects `HEAR_PHRASE`.
2. Eurydice captures a short focused phrase.
3. Eurydice transcribes it.
4. Eurydice identifies:
   - melody contour
   - interval
   - arpeggio shape
   - simple harmony hints
5. If confidence is low, it asks for one cleaner replay.

### Read and Play Flow

1. User imports or shows a short score segment.
2. Eurydice renders the notation.
3. Eurydice can read it aloud.
4. Eurydice can play it back as symbolic output.
5. User performs it back.
6. Eurydice compares the attempt and highlights mistakes.

## Why This Can Win

### Existing Products Prove Demand

The category is real, but still fragmented:

- **Yousician** already markets real-time feedback and claims:
  - **20 million monthly users**
  - **2,000+ songs**
  - **9,000+ lessons**
  - **1,500+ exercises**
- **Soundslice** already offers score scanning from PDFs and photos into interactive notation.

These products validate demand, but they do not fully combine:

- live conversation
- score reading
- adaptive lesson planning
- bar-by-bar evaluation
- multimodal tutoring in one agent loop

### Differentiation

Eurydice’s wedge is:

- one voice-first agent
- score-aware
- performance-aware
- confidence-aware
- pedagogically adaptive

That is more compelling than “another tuner” or “another scanner.”

## Current Market Framing

The current market appears to cluster into separate buckets:

- **Interactive practice apps**: good at listening and scoring basic performance
- **Notation viewers/scanners**: good at ingesting scores
- **Content platforms**: good at hosting tabs, lessons, and songs
- **Generative tools**: good at creating examples, but not at tutoring

Eurydice should sit above those as an orchestration layer: a tutor that uses notation, listening, and lesson planning together.

## Why Google

Google is the strongest fit for this project because the stack maps directly to the product:

### Gemini Live API

Gemini Live is the core tutor interface:

- low-latency voice interaction
- camera input
- turn-taking
- interruptions
- continuous multimodal context

This is what makes Eurydice feel like a teacher instead of a form.

### Vertex AI + Lyria 2

Lyria is not the source of truth for notation, but it is valuable for:

- generated exercises
- backing tracks
- example phrases
- ear-training prompts

### Cloud Run

Cloud Run fits the challenge and product well:

- quick iteration
- low-ops deployment
- easy secret integration
- appropriate for a multimodal web backend

### Firebase

Firebase keeps auth simple for a challenge project while still giving a production-grade entry point.

### Cloud SQL

Cloud SQL gives a stable session and lesson state store:

- saved scores
- attempts
- progress
- lesson continuity

## Product Decisions

### Brand

**Eurydice** is the product name.

Rationale:

- musical and mythic, but still elegant
- evokes guidance through uncertainty
- distinct from the accessibility-first Janey Mac domain
- flexible enough for a premium music tutor identity

### Experience Principles

1. **One action at a time**
   - Eurydice should guide the next best step, not expose a pile of tools.
2. **Confidence before authority**
   - if recognition is weak, ask for a replay instead of pretending.
3. **Symbolic truth over vague inference**
   - notation, MIDI, and structured note models are the product backbone.
4. **Short teaching loops**
   - one bar, one phrase, one correction.
5. **Voice first**
   - the experience should feel like a real tutor conversation.

### Accuracy Policy

For the core product, accuracy matters more than speed:

- exact symbolic handling when possible
- monophonic-first where reliability is highest
- confidence thresholds before feedback
- explicit replay prompts when evidence is weak

This is why stronger pitch engines are worth adding.

## Technical Architecture

### Platform Layer (Shared)

- FastAPI backend
- Cloud Run deployment
- Firebase Auth
- Cloud SQL persistence
- shared websocket/live session transport

### Music Domain Layer

- music session runtime
- phrase transcription
- symbolic score import
- notation rendering
- performance comparison
- lesson flow orchestration

### Symbolic Core

Authoritative representations:

- `MusicXML` as current interchange
- `MIDI` as practice/playback output
- `MNX` as future-facing structured notation target

### Notation Rendering

- **Verovio** as the primary notation renderer

### Audio Intelligence

Near-term:

- current lightweight monophonic transcription path

Next quality upgrades:

- **FastYIN** for stronger real-time pitch tracking
- **CREPE** as a higher-accuracy verification pass for focused clips

### Live Flow Split

The right split is:

- **Gemini Live** for tutoring, framing, explanation, and lesson guidance
- **deterministic local music analysis** for pitch/phrase comparison

That avoids asking the LLM to hallucinate exact note content from noisy audio.

## Why FastYIN and CREPE Matter

The current stack proves the workflow, but not yet the accuracy ceiling.

### FastYIN

Best use:

- low-latency pitch estimation
- stable monophonic note tracking
- better onset + pitch detection in real practice loops

### CREPE

Best use:

- higher-accuracy pitch confirmation on short captured clips
- rescoring or validating hard cases
- improving confidence before spoken feedback

### Product Decision

Eurydice should likely use:

- FastYIN for real-time candidate tracking
- CREPE for confirmation on the focused clip when accuracy matters

That is aligned with the quality-first product standard.

## User Stories

### Beginner Guitar Student

- As a beginner guitarist, I want Eurydice to break a song into small practice units so I can learn without being overwhelmed.

### Returning Adult Pianist

- As an adult pianist returning after years away, I want Eurydice to read a short score passage, play it, and tell me exactly which note or rhythm I missed.

### Ear Training Learner

- As a learner training intervals and arpeggios, I want Eurydice to listen to what I play and tell me what shape I produced, then suggest the next drill.

### Teacher Support

- As a teacher, I want to provide a simple phrase and let Eurydice run repetition and feedback loops between lessons.

### Accessible Music Learner

- As a low-vision learner, I want spoken guidance, score framing help, and note-level feedback without relying on dense visual UI.

## Success Metrics

### Product Metrics

- score import to render success rate
- phrase transcription confidence rate
- compare loop completion per phrase
- replay-request rate
- time to first correct bar
- lesson completion rate

### Challenge Demo Metrics

For the challenge demo, the key proof points are:

- one end-to-end lesson run completes
- live voice guidance feels immediate
- score rendering works
- compare feedback is visibly tied to the notation
- the agent advances the learner through a real practice loop

## Concrete Demo Standard

The demo should prove this exact narrative:

1. User asks for help learning a simple phrase.
2. Eurydice accepts a score line or image.
3. Eurydice prepares and renders the notation.
4. Eurydice explains what to play.
5. User plays one bar.
6. Eurydice compares the take.
7. Eurydice highlights the exact issue.
8. User retries.
9. Eurydice confirms the correction and advances.

If that loop works cleanly, the project is compelling.

## Challenge-Relevant Stats

- The **Gemini Live Agent Challenge** rules explicitly position the Live Agents category around real-time voice + vision assistants, including tutoring examples.
- The Devpost page currently shows **508 participants** as of **March 3, 2026**.
- The current challenge deadline is **March 16, 2026**.
- Gemini Live documented session limits include:
  - **up to 15 minutes** for audio-only sessions
  - **up to 2 minutes** for audio + video sessions
- Lyria 2 documentation currently specifies:
  - up to **4** generated samples per request
  - clips of about **32.8 seconds**
  - **48 kHz WAV**
  - price listed as **$0.06 per 30 seconds**

These are useful design constraints for the demo and architecture.

## Non-Goals (For Challenge Scope)

To stay competitive, Eurydice should **not** try to solve everything now:

- full polyphonic transcription for all instruments
- perfect chord-voicing recognition in noisy live audio
- full teacher marketplace
- DAW integration
- advanced composition environment

The winning scope is a focused, excellent guided practice loop.

## Immediate Build Priorities

1. Improve monophonic recognition quality with FastYIN, then CREPE-assisted confirmation.
2. Unify the `/music` interaction into one guided flow.
3. Make `READ_SCORE` and `COMPARE_PERFORMANCE` feel like one lesson progression.
4. Improve score-reading from camera input.
5. Make lesson planning explicit:
   - choose bar
   - perform
   - evaluate
   - repeat or advance

## Working Standard

When making product or engineering decisions, default to this question:

> Does this make Eurydice feel more like a real teacher guiding a student through a song, from first look to successful performance?

If the answer is no, it is probably not the right priority for the challenge build.

## References

- Gemini Live Agent Challenge rules: https://geminiliveagentchallenge.devpost.com/rules
- Gemini Live Agent Challenge page: https://geminiliveagentchallenge.devpost.com/
- Vertex AI Live API overview: https://cloud.google.com/vertex-ai/generative-ai/docs/live-api
- Vertex AI Live API session limits: https://cloud.google.com/vertex-ai/generative-ai/docs/live-api/streamed-conversations
- Lyria 2 model overview: https://cloud.google.com/vertex-ai/generative-ai/docs/models/lyria/lyria-002
- Lyria music generation reference: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/lyria-music-generation
- Yousician: https://yousician.com/
- Soundslice sheet music scanner: https://www.soundslice.com/sheet-music-scanner/
- Soundslice: https://www.soundslice.com/
- W3C MNX: https://github.com/w3c/mnx
