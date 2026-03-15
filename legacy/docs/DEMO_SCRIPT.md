# Eurydice Demo Script

Target runtime:
- 3 minutes 15 seconds to 3 minutes 45 seconds

Goal:
- Prove that Eurydice is a real-time multimodal music tutor, not just a chatbot or a pitch detector.

## Before Recording

Prepare these assets first:
- a very short score line or one stable bar,
- one instrument or voice input path you have already tested,
- a deployed Cloud Run environment,
- a backup take in case camera-based score reading is unstable.

Use the shortest stable flow.

## Script

### 0:00-0:20 The hook

Say:

> Learning an instrument is frustrating because most tools only solve one slice of the problem. Eurydice is a real-time music tutor that can hear a student play, read the score, and coach them bar by bar with Gemini Live.

Show:
- the app already open,
- the workspace,
- the score input area.

### 0:20-0:45 The problem and setup

Say:

> I am going to give Eurydice a simple phrase, let it prepare the lesson, and then I will play one bar so it can compare my take against the notation.

Show:
- entering or selecting a short score,
- clicking the lesson preparation action,
- the notation render appearing.

### 0:45-1:30 The multimodal moment

Say:

> Now I start the live session and ask for help like a real student would.

Show:
- start session,
- brief voice request,
- tutor response,
- if stable, briefly show camera mode or score framing,
- otherwise stay on the prepared score and live audio path.

Keep this part short. The point is to prove live interaction immediately.

### 1:30-2:20 The first take and analysis

Say:

> I will play the bar once, and Eurydice will compare what it heard against the target notes and rhythm.

Show:
- first take,
- comparison result,
- structured feedback panel,
- one concrete issue such as timing drift, hesitation, or clipped note length.

Narrate the result:

> Instead of vague praise, it tells me exactly what went wrong and what to fix next.

### 2:20-3:00 The retry

Say:

> I’ll try again using that feedback.

Show:
- second take,
- improved comparison,
- the lesson advancing or the feedback becoming cleaner.

Narrate:

> That closed-loop correction is the core of Eurydice. It listens, evaluates, explains, and adapts.

### 3:00-3:30 The stack and deployment proof

Say:

> Under the hood, Eurydice uses Gemini Live for real-time tutoring, deterministic music analysis for grounded correctness, and it is deployed on Google Cloud Run.

Show:
- architecture diagram from the README, or
- a quick cut to Cloud Run logs / dashboard, or
- one slide with Cloud Run, Vertex AI, and Cloud SQL called out.

### 3:30-3:45 The close

Say:

> Eurydice turns music practice into a real tutoring loop. Instead of only hearing notes, it helps a student understand what to fix and what to do next.

End on:
- the successful retry,
- the structured assessment,
- or the advanced lesson state.

## Recording Notes

Keep:
- one learner scenario,
- one clear mistake,
- one clear correction,
- one short deployment proof moment.

Cut:
- long sign-in flows,
- feature tours,
- anything that requires explanation before it feels useful,
- unstable camera segments if they distract from the main loop.

## Backup Version

If you need a safer recording path:
1. Use typed score input instead of camera score reading.
2. Keep the live session active so the Gemini Live proof remains visible.
3. Demo the compare loop and structured feedback as the centerpiece.

That is still a strong submission.
