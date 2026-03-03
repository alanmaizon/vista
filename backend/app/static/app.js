import { appState, elements } from "./state.js";
import {
  setAuthStatus,
  setSessionStatus,
  sessionRunning,
  primaryActionState,
  updatePrimaryActionButton,
  updateGoalHint,
  updateCaptureGuidance,
  refreshMediaButtons,
  updateMusicFlowHint,
  appendCaption,
  resetLessonFlow,
} from "./ui.js";
import { signIn, loadClientConfig } from "./api.js";
import { captureOneShotPcmClip, toBase64 } from "./audio.js";
import { enableMicCapture, disableMicCapture, syncVisualCapture, captureScreenshot } from "./media.js";
import { renderScoreNoteStrip, usesDeterministicLivePhraseCapture } from "./music-score.js";
import {
  transcribeOneShotClip,
  prepareScoreFlow,
  startCameraScoreReadFlow,
  runGuidedLessonAction,
  comparePerformanceClip,
} from "./music-lesson.js";
import { startSession, stopSession } from "./session.js";

elements.signIn.addEventListener("click", async () => {
  try {
    await signIn();
  } catch (error) {
    setAuthStatus(error.message || "Sign-in failed.");
  }
});

elements.start.addEventListener("click", async () => {
  const action = primaryActionState();

  try {
    if (action === "confirm") {
      if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
        return;
      }
      appState.assistantResponseReady = false;
      updatePrimaryActionButton();
      if (usesDeterministicLivePhraseCapture()) {
        setSessionStatus("Recording phrase...");
        const clip = await captureOneShotPcmClip({ durationMs: 2400 });
        if (!clip.length) {
          throw new Error("No phrase was captured.");
        }
        setSessionStatus("Analysing phrase...");
        appState.ws.send(
          JSON.stringify({
            type: "client.confirm",
            mime: "audio/pcm;rate=16000",
            data_b64: toBase64(clip),
          })
        );
      } else {
        appState.ws.send(JSON.stringify({ type: "client.confirm" }));
      }
      return;
    }

    if (action === "transcribe") {
      await transcribeOneShotClip();
      return;
    }

    if (action === "prepare-score") {
      await prepareScoreFlow();
      return;
    }

    if (action === "camera-score") {
      await startCameraScoreReadFlow();
      return;
    }

    if (action === "guided-lesson") {
      await runGuidedLessonAction();
      return;
    }

    if (action === "compare") {
      await comparePerformanceClip();
      return;
    }

    if (action === "stop") {
      await stopSession({ notifyServer: true });
      return;
    }

    await startSession();
  } catch (error) {
    appendCaption("Error", error.message || "Unable to start the session.");
    setSessionStatus(action === "start" ? "Start failed." : "Action failed.");
    if (action === "start") {
      await stopSession({ notifyServer: false });
    }
  }
});

elements.micToggle.addEventListener("click", async () => {
  appState.micEnabled = !appState.micEnabled;
  try {
    if (sessionRunning()) {
      if (appState.micEnabled) {
        if (!usesDeterministicLivePhraseCapture()) {
          await enableMicCapture();
        }
      } else {
        await disableMicCapture();
      }
    }
  } catch (error) {
    appState.micEnabled = !appState.micEnabled;
    appendCaption("Error", error.message || "Unable to update microphone.");
  }
  refreshMediaButtons();
  updateCaptureGuidance();
});

elements.cameraToggle.addEventListener("click", async () => {
  const nextValue = !appState.cameraEnabled;
  appState.cameraEnabled = nextValue;
  if (nextValue) {
    appState.screenEnabled = false;
  }
  try {
    if (sessionRunning()) {
      await syncVisualCapture();
    }
  } catch (error) {
    appState.cameraEnabled = !nextValue;
    appendCaption("Error", error.message || "Unable to update camera.");
  }
  refreshMediaButtons();
  updateCaptureGuidance();
});

elements.screenToggle.addEventListener("click", async () => {
  const nextValue = !appState.screenEnabled;
  appState.screenEnabled = nextValue;
  if (nextValue) {
    appState.cameraEnabled = false;
  }
  try {
    if (sessionRunning()) {
      await syncVisualCapture();
    }
  } catch (error) {
    appState.screenEnabled = !nextValue;
    appendCaption("Error", error.message || "Unable to update screen sharing.");
  }
  refreshMediaButtons();
  updateCaptureGuidance();
});

elements.snapshot.addEventListener("click", async () => {
  await captureScreenshot();
});

elements.mode.addEventListener("change", () => {
  resetLessonFlow({ keepPrepared: true });
  appState.cameraScoreImportPending = false;
  updateGoalHint();
  updateCaptureGuidance();
  updateMusicFlowHint();
  renderScoreNoteStrip();
  updatePrimaryActionButton();
});
if (elements.scoreLine) {
  elements.scoreLine.addEventListener("input", () => {
    if (appState.activeMusicScoreId || appState.scorePrepared) {
      appState.musicScoreDirty = true;
      appState.scorePrepared = false;
    }
    appState.activeMusicMeasures = [];
    resetLessonFlow({ keepPrepared: false });
    updatePrimaryActionButton();
    updateMusicFlowHint();
    renderScoreNoteStrip();
  });
}
const settingsToggle = document.getElementById("settings-toggle");
const settingsDropdown = document.getElementById("settings-dropdown");
if (settingsToggle && settingsDropdown) {
  settingsToggle.addEventListener("click", () => {
    const isOpen = !settingsDropdown.classList.contains("is-hidden");
    settingsDropdown.classList.toggle("is-hidden", isOpen);
    settingsToggle.setAttribute("aria-expanded", String(!isOpen));
  });
  document.addEventListener("click", (event) => {
    if (!settingsToggle.contains(event.target) && !settingsDropdown.contains(event.target)) {
      settingsDropdown.classList.add("is-hidden");
      settingsToggle.setAttribute("aria-expanded", "false");
    }
  });
}

updateGoalHint();
updateCaptureGuidance();
updatePrimaryActionButton();
refreshMediaButtons();
renderScoreNoteStrip();
updateMusicFlowHint();
void loadClientConfig();
