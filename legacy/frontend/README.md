# Eurydice Live Frontend

This frontend is intentionally small. It targets the reset live-agent backend and avoids the older multi-panel lesson workspace.

Active app flow:
- Build a session profile
- Open `WS /ws/live`
- Stream microphone audio
- Optionally stream camera frames
- Play assistant audio
- Show transcript, runtime state, and summary

Primary files:
- `src/App.jsx`
- `src/hooks/useLiveAgentApp.js`
- `src/components/LiveAgentWorkspace.jsx`
- `src/components/MarbleSphere.tsx`
- `src/lib/liveAudioRouter.js`
- `src/lib/liveAudioPlayback.js`
- `src/lib/audioCapture.js`

Useful commands:
- `npm run dev`
- `npm run lint`
- `npm run test`
- `npm run build`

Backend contract:
- `GET /api/runtime`
- `GET /api/runtime/debug`
- `POST /api/live/session-profile`
- `WS /ws/live`

For the exact message shapes, use [docs/LIVE_BACKEND_CONTRACT.md](../docs/LIVE_BACKEND_CONTRACT.md).
