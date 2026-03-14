# Eurydice Final Submission Playbook

This is the final-week plan for shipping Eurydice cleanly for the Gemini Live Agent Challenge.

Challenge deadline:
- March 16, 2026 at 5:00 PM PT

Guiding rule:
- Do not add new feature surface unless it directly improves demo reliability.
- Prioritize story clarity, deployment proof, and one polished end-to-end lesson run.

## The 4-Step Plan

### 1. Freeze scope and lock the story

Use one sentence everywhere:

> Eurydice is a real-time multimodal music tutor that hears a student play, reads the score, and gives structured bar-by-bar feedback using Gemini Live.

The only demo loop that matters:
1. User asks for help with a simple phrase.
2. Eurydice prepares and renders notation.
3. User plays one bar.
4. Eurydice compares the take and explains the issue.
5. User retries.
6. Eurydice confirms the correction and advances.

This matches the challenge demo standard already captured in [`docs/EURYDICE_CHALLENGE_BRIEF.md`](./EURYDICE_CHALLENGE_BRIEF.md).

### 2. Prepare the proof pack

Every submission should make the three required criteria easy to verify.

Gemini model:
- Live model config is defined in `backend/app/settings.py`.
- Deployment guidance explicitly pins `gemini-live-2.5-flash-native-audio` in [`docs/DEPLOYMENT.md`](./DEPLOYMENT.md).

Google GenAI SDK or ADK:
- Live bridge prefers ADK and falls back to the direct Vertex websocket bridge in `backend/app/live/bridge.py`.
- Memory embeddings use `google.genai.Client` in `backend/app/memory/embeddings.py`.

Google Cloud deployment:
- Architecture and deployment target are documented in [`README.md`](../README.md) and [`docs/DEPLOYMENT.md`](./DEPLOYMENT.md).
- Backend is designed for Cloud Run with Cloud SQL, Secret Manager, and Vertex AI.

Proof assets to gather now:
- One short screen recording from Google Cloud Console showing the Cloud Run service and recent logs.
- One screenshot of the Cloud Run service health page or revisions page.
- One screenshot or exported diagram from the README architecture section.
- One repo link to the live bridge and one repo link to the deployment doc.

Suggested repo links for the Devpost form:
- `README.md`
- `docs/DEPLOYMENT.md`
- `docs/live-tutor-architecture.md`
- `backend/app/live/bridge.py`
- `backend/app/memory/embeddings.py`

### 3. Record the demo for judges

Keep the video under 4 minutes and show the multimodal interaction immediately.

Recording priorities:
- Start with the working product, not slides.
- Show voice, score, and audio analysis in the same flow.
- Use one learner problem and one clean correction cycle.
- If anything is flaky, cut it from the demo.

Use this exact supporting asset:
- [`docs/DEMO_SCRIPT.md`](./DEMO_SCRIPT.md)

Non-negotiable moments to capture:
- Start live session.
- Show that the tutor listens and responds in real time.
- Show score preparation or reading.
- Show deterministic compare feedback tied to a bar or notes.
- Show the learner improve on the retry.
- End with why the product matters, not with a long technical recap.

### 4. Submit early and leave time for polish

Submit before the deadline, then use the remaining time for edits.

Final checklist:
- README intro is accurate and easy to skim.
- Architecture diagram is easy to find.
- Demo link works without extra permissions.
- Deployment proof link works.
- Repo includes clear local run instructions.
- Submission text states the problem, the multimodal interaction, and the Google Cloud deployment clearly.
- All screenshots and video uploads are visible from an incognito browser.

Recommended final-order workflow:
1. Upload the demo video.
2. Upload deployment proof.
3. Paste repo links.
4. Fill in project description.
5. Re-open the submitted page and verify every link.

## Demo Fallback Plan

If the live demo becomes unstable near the deadline:
- Keep the live audio path.
- Remove optional camera moments unless they are stable.
- Use a prepared short score line instead of live score reading.
- Show the compare loop and structured feedback as the core proof.

Better to submit one excellent guided lesson loop than three half-working modes.

## Judge-Facing Talking Points

Use these themes in the submission form and narration:
- Eurydice is not just transcription. It is a closed-loop tutor.
- Gemini Live handles the real-time conversation layer.
- Deterministic music tools ground musical correctness.
- Google Cloud Run hosts the deployed backend.
- Cloud SQL, Secret Manager, and Vertex AI support the production-style stack.
- The strongest product moment is structured feedback, not a flashy music demo.

## Last 24 Hours

Only do these tasks:
- fix bugs that affect the demo,
- tighten narration,
- improve README clarity,
- improve submission proof,
- rehearse the exact demo path you will record.

Do not:
- start a new training pipeline,
- redesign the UI,
- add a second hero workflow,
- rewrite major architecture.
