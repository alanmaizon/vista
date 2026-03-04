import { appState, elements, skillHints, skillCaptureRules } from "./state.js";
import { renderButton } from "./icons.js";
import { activeMeasureCount, usesDeterministicLivePhraseCapture } from "./music-score.js";

export function setAuthStatus(message) {
  elements.authStatus.textContent = message;
  console.info(`[${appState.brand}][Auth]`, message);
}

export function setSessionStatus(message) {
  elements.sessionStatus.textContent = message;
  console.info(`[${appState.brand}][Status]`, message);
}

export function setRiskBadge(mode) {
  elements.riskBadge.textContent = mode;
  elements.riskBadge.classList.remove("caution", "refuse");
  if (mode === "CAUTION") {
    elements.riskBadge.classList.add("caution");
  }
  if (mode === "REFUSE") {
    elements.riskBadge.classList.add("refuse");
  }
}

export function setRunningState(isRunning) {
  elements.start.disabled = false;
  if (!isRunning) {
    appState.assistantResponseReady = false;
  }
  updatePrimaryActionButton();
  refreshMediaButtons();
}

export function sessionRunning() {
  return Boolean(appState.ws && appState.ws.readyState === WebSocket.OPEN);
}

export function hasVisualSourceEnabled() {
  return appState.cameraEnabled || appState.screenEnabled;
}

export function setToggleButton(button, enabled, onLabel, offLabel, icon) {
  renderButton(button, {
    icon,
    label: enabled ? onLabel : offLabel,
    iconOnly: true,
  });
  button.classList.toggle("is-on", enabled);
}

export function primaryActionState() {
  if (!sessionRunning()) {
    if (appState.domain === "MUSIC") {
      if (elements.mode.value === "GUIDED_LESSON") {
        if (!hasFreshPreparedScore() || appState.musicScoreDirty) {
          if (!hasScoreDraft() && hasVisualSourceEnabled()) {
            return "camera-score";
          }
          return "guided-lesson";
        }
        return "guided-lesson";
      }
      if (
        elements.mode.value === "READ_SCORE" &&
        !hasFreshPreparedScore() &&
        !hasScoreDraft() &&
        hasVisualSourceEnabled()
      ) {
        return "camera-score";
      }
      if (musicModeUsesPreparedScore() && (!hasFreshPreparedScore() || appState.musicScoreDirty)) {
        return "prepare-score";
      }
      if (elements.mode.value === "HEAR_PHRASE") {
        return "transcribe";
      }
      if (elements.mode.value === "COMPARE_PERFORMANCE" && hasFreshPreparedScore()) {
        return "compare";
      }
    }
    return "start";
  }
  return appState.assistantResponseReady ? "confirm" : "stop";
}

export function musicModeUsesPreparedScore() {
  if (appState.domain !== "MUSIC") {
    return false;
  }
  return (
    elements.mode.value === "READ_SCORE" ||
    elements.mode.value === "COMPARE_PERFORMANCE" ||
    elements.mode.value === "GUIDED_LESSON"
  );
}

export function hasScoreDraft() {
  return Boolean(elements.scoreLine && elements.scoreLine.value.trim());
}

export function hasFreshPreparedScore() {
  return Boolean(appState.activeMusicScoreId && appState.scorePrepared && !appState.musicScoreDirty);
}

export function resetLessonFlow({ keepPrepared = true } = {}) {
  appState.lessonMeasureIndex = null;
  appState.lessonStage = "idle";
  appState.highlightedScoreNoteIndexes = [];
  appState.focusedScoreNoteIndex = null;
  if (!keepPrepared) {
    appState.scorePrepared = false;
  }
}

function applyPrimaryAction(cssClass, icon, label, disabled = false) {
  elements.start.classList.add(cssClass);
  renderButton(elements.start, { icon, label });
  elements.start.disabled = disabled;
}

export function updatePrimaryActionButton() {
  const state = primaryActionState();
  elements.start.classList.remove("primary", "accent", "danger");

  if (state === "confirm") {
    applyPrimaryAction(
      "accent",
      "confirm",
      usesDeterministicLivePhraseCapture() ? "Capture phrase" : "Confirm step",
    );
    return;
  }
  if (state === "transcribe") {
    applyPrimaryAction("primary", "analyze", "Hear phrase");
    return;
  }
  if (state === "camera-score") {
    applyPrimaryAction("primary", "camera", "Read score", !hasVisualSourceEnabled());
    return;
  }
  if (state === "guided-lesson") {
    elements.start.classList.add("primary");
    if (!hasFreshPreparedScore() || appState.musicScoreDirty) {
      applyPrimaryAction("primary", "confirm", "Prepare lesson", !hasScoreDraft());
      return;
    }
    if (appState.lessonStage === "awaiting-compare") {
      applyPrimaryAction("primary", "analyze", "Compare bar", !appState.micEnabled);
      return;
    }
    const finalBar = activeMeasureCount() > 0 && appState.lessonMeasureIndex === activeMeasureCount();
    renderButton(elements.start, {
      icon: "start",
      label:
        appState.lessonStage === "complete"
          ? "Restart lesson"
          : finalBar && appState.lessonStage === "reviewed"
            ? "Finish lesson"
            : "Next bar",
    });
    return;
  }
  if (state === "prepare-score") {
    applyPrimaryAction("primary", "confirm", "Prepare score", !hasScoreDraft());
    return;
  }
  if (state === "compare") {
    applyPrimaryAction("primary", "analyze", "Compare take");
    return;
  }
  if (state === "stop") {
    applyPrimaryAction("danger", "stop", "Stop session");
    return;
  }

  applyPrimaryAction("primary", "start", "Start session");
}

export function updateMusicFlowHint() {
  if (!elements.musicFlowHint || appState.domain !== "MUSIC") {
    return;
  }

  let message = "Use the main button for the next music action.";
  if (elements.mode.value === "HEAR_PHRASE") {
    message = "Use the main button to capture one focused phrase. Play immediately after pressing it.";
  } else if (elements.mode.value === "GUIDED_LESSON") {
    if (appState.cameraScoreImportPending) {
      message = "Show one short bar clearly. Eurydice is listening for a NOTE_LINE capture from the live score reader.";
    } else if (!hasFreshPreparedScore()) {
      if (hasScoreDraft()) {
        message = "Prepare the score, then Eurydice will guide you bar by bar.";
      } else if (hasVisualSourceEnabled()) {
        message = "Use the main button to read one short bar from camera, then Eurydice will prepare the lesson.";
      } else {
        message = "Add a score line or turn on camera to capture one bar from the sheet before starting the lesson.";
      }
    } else if (appState.lessonStage === "awaiting-compare") {
      message = `Play bar ${appState.lessonMeasureIndex || 1}, then use the main button to compare your take.`;
    } else if (appState.lessonStage === "reviewed") {
      const finalBar = activeMeasureCount() > 0 && appState.lessonMeasureIndex === activeMeasureCount();
      message = finalBar
        ? "This was the last prepared bar. Use the main button to finish or replay it."
        : "Use the main button to move to the next bar.";
    } else {
      message = "Use the main button to begin the guided lesson at the first prepared bar.";
    }
  } else if (elements.mode.value === "COMPARE_PERFORMANCE") {
    if (hasFreshPreparedScore()) {
      message = "The score is prepared. Use the main button to record one take and compare it.";
    } else if (hasScoreDraft()) {
      message = "Enter or edit the score line, then use the main button to prepare the score before comparing.";
    } else {
      message = "Add a score line first, then use the main button to prepare and compare a take.";
    }
  } else if (elements.mode.value === "READ_SCORE") {
    if (hasFreshPreparedScore()) {
      message = "The score is prepared. Start a live session when you want spoken score guidance.";
    } else if (!hasScoreDraft() && hasVisualSourceEnabled()) {
      message = "Use the main button to capture one readable bar from camera, then Eurydice will prepare notation.";
    } else if (hasScoreDraft()) {
      message = "Enter a score line, then use the main button to prepare notation before asking Eurydice to read it.";
    } else {
      message = "Add a score line first, then use the main button to prepare notation.";
    }
  } else if (elements.mode.value === "SHEET_FRAME_COACH") {
    message = "Turn on the camera, then start a live session so Eurydice can help frame the sheet clearly.";
  }

  elements.musicFlowHint.textContent = message;
}

export function refreshMediaButtons() {
  setToggleButton(elements.micToggle, appState.micEnabled, "Microphone on", "Microphone off", "mic");
  setToggleButton(elements.cameraToggle, appState.cameraEnabled, "Camera on", "Camera off", "camera");
  setToggleButton(elements.screenToggle, appState.screenEnabled, "Screen share on", "Screen share off", "screen");
  renderButton(elements.snapshot, { icon: "snapshot", label: "Capture screenshot", iconOnly: true });
  elements.snapshot.disabled = !sessionRunning() || !hasVisualSourceEnabled();
}

export function markAssistantResponseReady() {
  if (appState.assistantResponseReady) {
    return;
  }
  appState.assistantResponseReady = true;
  updatePrimaryActionButton();
}

export function appendCaption(label, text) {
  console.info(`[${appState.brand}][${label}]`, text);
  const item = document.createElement("div");
  item.className = "caption";

  const heading = document.createElement("small");
  heading.textContent = label;
  item.appendChild(heading);

  const body = document.createElement("div");
  body.textContent = text;
  item.appendChild(body);

  elements.captions.prepend(item);
}

export function updateGoalHint() {
  const hint = skillHints[elements.mode.value] || "Describe what you need help with.";
  elements.goal.placeholder = hint;
}

export function getCaptureRule(modeOverride = elements.mode.value) {
  return skillCaptureRules[modeOverride] || null;
}

export function selectedSkillNeedsVisualSource(modeOverride = elements.mode.value) {
  return Boolean(getCaptureRule(modeOverride)?.requiresCamera);
}

export function updateCaptureGuidance() {
  const rule = getCaptureRule();
  if (appState.domain === "MUSIC" && elements.mode.value === "GUIDED_LESSON") {
    if (hasFreshPreparedScore()) {
      elements.captureHint.textContent =
        "Eurydice will guide one bar at a time. Use the main button to move to the next bar or compare the current take.";
    } else if (hasVisualSourceEnabled()) {
      elements.captureHint.textContent =
        "Use the camera to capture one clear bar from the sheet, or type a score line to prepare the lesson.";
    } else {
      elements.captureHint.textContent =
        "Type a score line or turn on camera to capture one bar from the sheet before starting the lesson.";
    }
  } else if (rule) {
    elements.captureHint.textContent = rule.hint;
  } else if (usesDeterministicLivePhraseCapture()) {
    elements.captureHint.textContent =
      "In HEAR_PHRASE live mode, use Capture phrase to record one short, clean replay for analysis.";
  } else {
    elements.captureHint.textContent =
      "Audio-first checks work without camera. Dense visual tasks need a clean close-up.";
  }

  if (selectedSkillNeedsVisualSource() && !hasVisualSourceEnabled()) {
    elements.cameraWarning.textContent =
      "Turn on camera or screen sharing for this skill. Audio-only mode cannot reliably answer a visual task.";
    return;
  }

  if (appState.screenEnabled) {
    elements.cameraWarning.textContent =
      "Screen sharing is active. Use Capture Screenshot when you want to send a still frame immediately.";
    return;
  }

  if (appState.cameraEnabled) {
    elements.cameraWarning.textContent =
      "Camera is active. Keep the frame simple: one item, one label, or one control at a time.";
    return;
  }

  elements.cameraWarning.textContent = "";
}
