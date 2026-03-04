/**
 * @module LessonStateMachine
 *
 * Lesson-flow orchestration and score-preparation state management.
 *
 * Manages the "guided lesson" lifecycle: preparing scores on the backend,
 * advancing through lesson steps bar-by-bar, and coordinating camera-based
 * score import.  Acts as the state machine that decides which API call
 * to make next based on the current lesson stage and score readiness.
 *
 * Extracted from music-lesson.js to separate high-level flow control
 * from audio processing and rendering concerns.
 */

import { appState, elements } from "../state.js";
import {
  setSessionStatus,
  appendCaption,
  hasFreshPreparedScore,
  hasVisualSourceEnabled,
  updatePrimaryActionButton,
  updateMusicFlowHint,
  resetLessonFlow,
} from "../ui.js";
import { readApiPayload } from "../api.js";
import { sanitizeInput } from "../sanitize.js";
import { toBase64, captureOneShotPcmClip } from "../audio.js";
import {
  flattenNotesFromMeasures,
  renderImportedScore,
  renderScoreSurface,
  renderScoreNoteStrip,
  setScoreOverlayState,
  buildScoreOverlayMarkersForState,
  focusLessonMeasure,
  activeMeasureCount,
} from "./RenderingEngine.js";
import { applyComparisonPayload } from "./AudioProcessor.js";
import { stopSession, startSession } from "../session.js";

export function applyPreparedScorePayload(payload) {
  appState.activeMusicScoreId = payload.score_id || null;
  appState.activeMusicMeasures = Array.isArray(payload.measures) ? payload.measures : [];
  appState.activeMusicNotes = Array.isArray(payload.expected_notes)
    ? payload.expected_notes
    : flattenNotesFromMeasures(payload.measures);
  appState.scorePrepared = true;
  appState.musicScoreDirty = false;
  appState.scoreLayoutHints = Array.isArray(payload.note_layout) ? payload.note_layout : [];
  resetLessonFlow();
  setScoreOverlayState({
    mode: "score-ready",
    summary: payload.render_backend === "VEROVIO" ? "Score rendered" : "MusicXML fallback",
    markers: buildScoreOverlayMarkersForState("score-ready"),
  });
  renderImportedScore(payload);
  renderScoreSurface(payload);
  renderScoreNoteStrip();
  appendCaption(
    "Render",
    payload.render_backend === "VEROVIO"
      ? "Rendered notation with Verovio."
      : "Verovio was unavailable, so MusicXML fallback is shown."
  );
  if (Array.isArray(payload.warnings)) {
    for (const warning of payload.warnings) {
      appendCaption("Warning", warning);
    }
  }
  setSessionStatus("Notation ready.");
  updatePrimaryActionButton();
  updateMusicFlowHint();
}

export function applyGuidedLessonStepPayload(payload) {
  if (payload.lesson_complete) {
    appState.lessonMeasureIndex = null;
    appState.lessonStage = "complete";
    appState.highlightedScoreNoteIndexes = [];
    appState.focusedScoreNoteIndex = null;
    setScoreOverlayState({
      mode: "match",
      summary: "Lesson complete.",
      markers: buildScoreOverlayMarkersForState("match"),
    });
    renderScoreNoteStrip();
    appendCaption("Lesson", payload.prompt);
    setSessionStatus(payload.status);
    updatePrimaryActionButton();
    updateMusicFlowHint();
    return;
  }

  appState.lessonMeasureIndex = payload.measure_index;
  appState.lessonStage = payload.lesson_stage;
  focusLessonMeasure(payload.measure_index, {
    start: payload.note_start_index,
    end: payload.note_end_index,
  });
  appendCaption("Lesson", payload.prompt);
  setSessionStatus(payload.status);
  updatePrimaryActionButton();
  updateMusicFlowHint();
}

export async function prepareScoreFlow(sourceTextOverride = null) {
  if (!appState.user) {
    throw new Error("Sign in before preparing a score.");
  }
  const sourceText = sanitizeInput(sourceTextOverride ?? elements.scoreLine?.value ?? "", { maxLength: 5000 });
  if (!sourceText) {
    throw new Error("Enter a score line before preparing it.");
  }

  setSessionStatus("Preparing score...");
  const idToken = await appState.user.getIdToken(true);
  const response = await fetch("/api/music/score/prepare", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      source_text: sourceText,
      source_format: "NOTE_LINE",
      time_signature: "4/4",
      persist: true,
    }),
  });

  const payload = await readApiPayload(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Score preparation failed with ${response.status}`);
  }

  applyPreparedScorePayload(payload);
}

export async function runGuidedLessonAction({ sourceTextOverride = null } = {}) {
  if (!appState.user) {
    throw new Error("Sign in before starting the guided lesson.");
  }

  const sourceText = sanitizeInput(sourceTextOverride ?? elements.scoreLine?.value ?? "", { maxLength: 5000 });
  const awaitingCompare = hasFreshPreparedScore() && appState.lessonStage === "awaiting-compare";
  let audioBase64 = null;

  if (awaitingCompare) {
    if (!appState.micEnabled) {
      throw new Error("Turn the microphone on before comparing this bar.");
    }
    setSessionStatus("Recording a comparison take...");
    const clip = await captureOneShotPcmClip({ durationMs: 2800 });
    if (!clip.length) {
      throw new Error("No audio was captured.");
    }
    audioBase64 = toBase64(clip);
    setSessionStatus("Comparing bar...");
  } else if (!hasFreshPreparedScore() || appState.musicScoreDirty) {
    if (!sourceText) {
      throw new Error("Enter a score line before preparing the lesson.");
    }
    setSessionStatus("Preparing lesson...");
  } else if (!activeMeasureCount()) {
    throw new Error("The prepared score does not contain readable bars yet.");
  } else {
    setSessionStatus("Loading next lesson step...");
  }

  const idToken = await appState.user.getIdToken(true);
  const response = await fetch("/api/music/lesson-action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      score_id: hasFreshPreparedScore() && !appState.musicScoreDirty ? appState.activeMusicScoreId : null,
      source_text: !hasFreshPreparedScore() || appState.musicScoreDirty ? sourceText : null,
      time_signature: "4/4",
      current_measure_index: appState.lessonMeasureIndex,
      lesson_stage: appState.lessonStage,
      audio_b64: audioBase64,
      mime: audioBase64 ? "audio/pcm;rate=16000" : undefined,
      max_notes: 12,
    }),
  });

  const payload = await readApiPayload(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Guided lesson step failed with ${response.status}`);
  }

  if (payload?.score) {
    applyPreparedScorePayload(payload.score);
  }
  if (payload?.lesson) {
    applyGuidedLessonStepPayload(payload.lesson);
  }
  if (payload?.comparison) {
    applyComparisonPayload(payload.comparison, {
      measureIndex: appState.lessonMeasureIndex || 1,
    });
  }
}

export async function handleCapturedScoreLine(noteLine) {
  appState.cameraScoreImportPending = false;
  if (elements.scoreLine) {
    elements.scoreLine.value = noteLine;
  }
  appState.musicScoreDirty = false;
  appendCaption("Score", `Captured score line: ${noteLine}`);
  await stopSession({ notifyServer: false });
  if (elements.mode.value === "GUIDED_LESSON") {
    await runGuidedLessonAction({ sourceTextOverride: noteLine });
    return;
  }
  setSessionStatus("Preparing captured score...");
  await prepareScoreFlow(noteLine);
}

export async function startCameraScoreReadFlow() {
  if (!hasVisualSourceEnabled()) {
    throw new Error("Turn on camera or screen sharing before reading a score from the sheet.");
  }
  appState.cameraScoreImportPending = true;
  setSessionStatus("Opening live score reader...");
  await startSession({
    sessionMode: "READ_SCORE",
    goalOverride:
      "Read one short bar from the visible sheet. If it is readable, emit NOTE_LINE: followed by a simple note line. If it is unclear, say SCORE_UNCLEAR.",
    requireVisual: true,
  });
}
