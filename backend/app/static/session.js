import { appState, elements } from "./state.js";
import {
  setRunningState,
  setRiskBadge,
  setSessionStatus,
  sessionRunning,
  appendCaption,
  markAssistantResponseReady,
  refreshMediaButtons,
  getCaptureRule,
  selectedSkillNeedsVisualSource,
  hasVisualSourceEnabled,
} from "./ui.js";
import { readApiPayload } from "./api.js";
import { sanitizeInput } from "./sanitize.js";
import { queuePlaybackChunk } from "./audio.js";
import { enableMicCapture, syncVisualCapture, stopMedia } from "./media.js";
import { renderSummary, usesDeterministicLivePhraseCapture } from "./music-score.js";
import { handleCapturedScoreLine } from "./music-lesson.js";

export async function createSession(idToken, { sessionMode = elements.mode.value, goalOverride = null } = {}) {
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      domain: appState.domain,
      mode: sessionMode,
      goal: sanitizeInput(goalOverride ?? elements.goal.value, { maxLength: 500 }) || null,
    }),
  });

  const payload = await readApiPayload(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Session create failed with ${response.status}`);
  }

  return payload;
}

export function createLiveSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${protocol}://${window.location.host}/ws/live`);
}

export function waitForSocketOpen(ws) {
  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener("error", () => reject(new Error("WebSocket connection failed")), {
      once: true,
    });
  });
}

export function attachSocketHandlers(ws) {
  ws.onmessage = async (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      appendCaption("Error", "Received an unreadable websocket message.");
      return;
    }

    switch (payload.type) {
      case "server.audio":
        markAssistantResponseReady();
        queuePlaybackChunk(payload.data_b64, payload.mime);
        break;
      case "server.text":
        if (appState.cameraScoreImportPending) {
          break;
        }
        markAssistantResponseReady();
        appendCaption("Live", payload.text);
        break;
      case "server.score_capture":
        await handleCapturedScoreLine(payload.note_line || "");
        break;
      case "server.score_unclear":
        appendCaption("Score", "The score is still unclear. Move closer, reduce glare, and center one short bar.");
        setSessionStatus("Sheet still unclear.");
        break;
      case "server.status":
        setRiskBadge(payload.mode || "NORMAL");
        if (payload.state === "caution") {
          appendCaption("Status", "CAUTION mode: stop moving and wait for conservative guidance.");
        } else if (payload.state === "refuse") {
          appendCaption("Status", "REFUSE mode: this task is blocked. Ask for a safer alternative.");
        } else {
          setSessionStatus(`Connected in ${payload.skill}.`);
        }
        break;
      case "server.summary":
        renderSummary(payload.bullets || []);
        await stopSession({ notifyServer: false });
        break;
      case "error":
        appendCaption("Error", payload.message || "Unknown error");
        setSessionStatus("Error.");
        await stopSession({ notifyServer: false });
        break;
      default:
        break;
    }
  };

  ws.onerror = () => {
    appendCaption("Error", "WebSocket connection error. Check your network and try again.");
    setSessionStatus("Connection error.");
  };

  ws.onclose = async () => {
    await stopMedia();
    appState.ws = null;
    appState.sessionId = null;
    appState.cameraScoreImportPending = false;
    setRunningState(false);
    refreshMediaButtons();
  };
}

export async function startSession({
  sessionMode = elements.mode.value,
  goalOverride = null,
  requireVisual = false,
} = {}) {
  if (!appState.user) {
    throw new Error("Sign in before starting a session.");
  }
  if (!appState.micEnabled && !hasVisualSourceEnabled()) {
    throw new Error("Turn on mic, camera, or screen sharing before starting.");
  }
  if ((requireVisual || selectedSkillNeedsVisualSource(sessionMode)) && !hasVisualSourceEnabled()) {
    throw new Error("Turn on camera or screen sharing for this skill, then show one item or panel at a time.");
  }

  elements.summary.innerHTML = "";
  appState.playbackCursor = 0;
  appState.assistantResponseReady = false;
  setRiskBadge("NORMAL");
  setSessionStatus("Creating session...");

  const idToken = await appState.user.getIdToken(true);
  const session = await createSession(idToken, { sessionMode, goalOverride });
  appState.sessionId = session.id;

  setSessionStatus("Opening live websocket...");
  let ws;
  try {
    ws = createLiveSocket();
  } catch (error) {
    setSessionStatus("Connection failed.");
    appendCaption("Error", "Unable to open WebSocket connection. Please check your network and try again.");
    throw new Error("WebSocket connection could not be established.");
  }
  appState.ws = ws;
  attachSocketHandlers(appState.ws);
  try {
    await waitForSocketOpen(appState.ws);
  } catch (error) {
    appState.ws = null;
    setSessionStatus("Connection failed.");
    appendCaption("Error", "WebSocket connection failed. The server may be unavailable. Please try again later.");
    throw error;
  }
  appState.ws.send(
    JSON.stringify({
      type: "client.init",
      token: idToken,
      session_id: session.id,
      mode: sessionMode,
    })
  );

  if (appState.micEnabled) {
    if (!usesDeterministicLivePhraseCapture(sessionMode)) {
      await enableMicCapture();
    }
  }
  await syncVisualCapture();

  const captureRule = getCaptureRule(sessionMode);
  if (captureRule) {
    appendCaption("Setup", captureRule.hint);
    if (appState.domain === "MUSIC" && sessionMode === "READ_SCORE") {
      appendCaption("Setup", "Score reading is text-first. Keep one short bar centered until Eurydice captures a NOTE_LINE.");
    }
  } else if (usesDeterministicLivePhraseCapture(sessionMode)) {
    appendCaption(
      "Setup",
      "Capture phrase records a short focused replay. Play immediately after pressing it."
    );
  } else if (appState.domain === "MUSIC" && sessionMode === "GUIDED_LESSON") {
    appendCaption("Setup", "This lesson loop is deterministic-first. Use the main button to move bar by bar.");
  } else if (appState.domain === "MUSIC" && sessionMode === "COMPARE_PERFORMANCE") {
    appendCaption("Setup", "Comparison is deterministic-first. Use the prepared score and compare one take at a time.");
  } else if (!hasVisualSourceEnabled()) {
    appendCaption("Setup", "Audio-only mode is active. Use a short spoken question.");
  }
  if (appState.screenEnabled) {
    appendCaption("Setup", "Screen sharing is active. Use Capture Screenshot for an extra still frame.");
  }

  setRunningState(true);
  setSessionStatus("Live session running.");
}

export async function stopSession({ notifyServer = true } = {}) {
  const activeSocket = appState.ws;
  if (notifyServer && activeSocket && activeSocket.readyState === WebSocket.OPEN) {
    activeSocket.send(JSON.stringify({ type: "client.stop" }));
    window.setTimeout(() => {
      if (activeSocket.readyState === WebSocket.OPEN) {
        activeSocket.close();
      }
    }, 1200);
  }

  await stopMedia();
  if (activeSocket) {
    appState.ws = null;
    appState.sessionId = null;
    if (!notifyServer && activeSocket.readyState < WebSocket.CLOSING) {
      activeSocket.close();
    }
  }
  setRunningState(false);
  setSessionStatus("Stopped.");
}
