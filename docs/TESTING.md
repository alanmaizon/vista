# Testing

This is the current test path for the reset Eurydice Live app.

## What is actively covered

- **Backend pytest suite**
  - Health and runtime endpoints
  - Session profile normalization
  - `/ws/live` init, audio, video, text, and shutdown flow
  - Live bridge event sequencing
  - Conversation turn merging
  - Runtime state and prompt behavior

- **Frontend checks**
  - ESLint
  - Vitest unit tests for audio capture and live audio routing
  - Production build via Vite

## Current gaps

- No browser E2E test yet
- No single-command root test runner yet
- Legacy music HTTP tests are still in the repo but are intentionally skipped in the live-agent reset

## Fast path

Run these from the repo root:

```bash
python3 -m pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

If all four pass, the current live-agent app is in good shape for local verification or deploy.

## Focused runs

### Backend

```bash
python3 -m pytest backend/tests/test_websocket.py -q
python3 -m pytest backend/tests/test_live_bridge_tools.py -q
python3 -m pytest backend/tests/test_conversation_manager.py -q
```

Use these when working on the live session contract, bridge behavior, or transcript assembly.

### Frontend

```bash
npm --prefix frontend run test
```

Current frontend unit coverage is concentrated in:

- `frontend/src/lib/__tests__/audioCapture.test.js`
- `frontend/src/lib/__tests__/liveAudioRouter.test.js`

## Notes

- Backend tests are designed to run locally without talking to the live Gemini service.
- Some backend modules use `pytest.importorskip(...)` for optional dependencies.
- You may still see the known `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope`. It is noisy, but it does not currently fail the suite.
- `backend/tests/test_music_transcription.py` is intentionally skipped because it belongs to the retired pre-reset HTTP surface.

## Recommended pre-ship check

Before deploy or demo recording, run:

```bash
python3 -m pytest backend/tests -q && \
npm --prefix frontend run lint && \
npm --prefix frontend run test && \
npm --prefix frontend run build
```

Then do one manual browser pass:

1. Start a session
2. Confirm the greeting arrives
3. Speak one prompt and confirm a reply comes back
4. Toggle camera and confirm frames are accepted
5. End the session and confirm the recap view appears
