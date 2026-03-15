/**
 * @module AudioProcessor
 *
 * Audio capture, transcription, and performance comparison logic.
 *
 * Handles one-shot clip transcription via the backend transcription API
 * and performance-comparison workflows that record a short phrase and
 * send it to the backend for note-level comparison against a prepared score.
 *
 * Extracted from music-lesson.js to isolate audio-processing concerns
 * from lesson-flow orchestration.
 */

import { appState, elements, musicExpectedKinds } from "../state.js";
import {
  sessionRunning,
  setSessionStatus,
  appendCaption,
  updatePrimaryActionButton,
  updateMusicFlowHint,
} from "../ui.js";
import { readApiPayload } from "../api.js";
import { toBase64, captureOneShotPcmClip } from "../audio.js";
import {
  renderMusicAnalysis,
  renderPerformanceComparison,
  renderScoreNoteStrip,
  setScoreOverlayState,
  buildScoreOverlayMarkersForState,
  noteOffsetForMeasure,
  noteRangeForMeasure,
} from "./RenderingEngine.js";

export function applyComparisonPayload(payload, { measureIndex = null } = {}) {
  const measureOffset = measureIndex ? noteOffsetForMeasure(measureIndex) : 0;
  const overlayMode = payload.needs_replay ? "replay" : payload.match ? "match" : "difference";
  let overlayMarkers = buildScoreOverlayMarkersForState(overlayMode, payload.comparisons);
  if (measureIndex) {
    overlayMarkers = buildScoreOverlayMarkersForState("score-ready");
    const range = noteRangeForMeasure(measureIndex);
    if (payload.needs_replay) {
      for (let index = range.start; index < range.end; index += 1) {
        overlayMarkers[index] = { state: "replay" };
      }
    } else if (Array.isArray(payload.comparisons)) {
      payload.comparisons.forEach((item, index) => {
        if (range.start + index >= overlayMarkers.length) {
          return;
        }
        if (!item?.pitch_match) {
          overlayMarkers[range.start + index] = { state: "pitch" };
        } else if (!item?.rhythm_match) {
          overlayMarkers[range.start + index] = { state: "rhythm" };
        } else {
          overlayMarkers[range.start + index] = { state: "match" };
        }
      });
    }
  }
  if (!measureIndex && Array.isArray(payload.expected_notes)) {
    appState.activeMusicNotes = payload.expected_notes;
  }
  appState.highlightedScoreNoteIndexes = payload.needs_replay
    ? []
    : Array.isArray(payload.comparisons)
      ? payload.comparisons
          .filter((item) => !item.pitch_match || !item.rhythm_match)
          .map((item) => measureOffset + Math.max(0, Number(item.index || 1) - 1))
      : [];
  appState.focusedScoreNoteIndex = appState.highlightedScoreNoteIndexes[0] ?? null;
  setScoreOverlayState({
    mode: overlayMode,
    summary: payload.summary || "",
    markers: overlayMarkers,
  });
  renderScoreNoteStrip();
  renderPerformanceComparison(payload);
  appendCaption("Compare", payload.summary || "Comparison complete.");
  if (payload.needs_replay) {
    appendCaption("Replay", "Replay the phrase slowly and clearly before trusting this comparison.");
  }
  if (Array.isArray(payload.mismatches)) {
    for (const mismatch of payload.mismatches) {
      appendCaption("Difference", mismatch);
    }
  }
  if (Array.isArray(payload.warnings)) {
    for (const warning of payload.warnings) {
      appendCaption("Warning", warning);
    }
  }
  if (measureIndex) {
    appState.lessonMeasureIndex = measureIndex;
    appState.lessonStage = payload.needs_replay || !payload.match ? "awaiting-compare" : "reviewed";
  }
  setSessionStatus(payload.needs_replay ? "Replay requested." : "Comparison ready.");
  updatePrimaryActionButton();
  updateMusicFlowHint();
}

export async function comparePerformanceClip({ measureIndex = null } = {}) {
  if (sessionRunning()) {
    throw new Error("Stop the live session before comparing a take.");
  }
  if (!appState.user) {
    throw new Error("Sign in before comparing a performance.");
  }
  if (!appState.activeMusicScoreId) {
    throw new Error("Import a score before comparing a take.");
  }
  if (!appState.micEnabled) {
    throw new Error("Turn the microphone on before comparing a take.");
  }

  setSessionStatus("Recording a comparison take...");
  const clip = await captureOneShotPcmClip({ durationMs: 2800 });
  if (!clip.length) {
    throw new Error("No audio was captured.");
  }

  setSessionStatus("Comparing performance...");
  const idToken = await appState.user.getIdToken(true);
  const response = await fetch(`/api/music/score/${appState.activeMusicScoreId}/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      audio_b64: toBase64(clip),
      mime: "audio/pcm;rate=16000",
      max_notes: 12,
      measure_index: measureIndex,
    }),
  });

  const payload = await readApiPayload(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Comparison failed with ${response.status}`);
  }

  applyComparisonPayload(payload, { measureIndex });
  return payload;
}

export async function transcribeOneShotClip() {
  if (sessionRunning()) {
    throw new Error("Stop the live session before running a one-shot transcription.");
  }
  if (!appState.user) {
    throw new Error("Sign in before running transcription.");
  }
  if (!appState.micEnabled) {
    throw new Error("Turn the microphone on before running transcription.");
  }

  setSessionStatus("Recording a short phrase...");
  const clip = await captureOneShotPcmClip();
  if (!clip.length) {
    throw new Error("No audio was captured.");
  }

  setSessionStatus("Transcribing phrase...");
  const idToken = await appState.user.getIdToken(true);
  const response = await fetch("/api/music/transcribe", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      audio_b64: toBase64(clip),
      mime: "audio/pcm;rate=16000",
      expected: musicExpectedKinds[elements.mode.value] || "AUTO",
      max_notes: 8,
    }),
  });

  const payload = await readApiPayload(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Transcription failed with ${response.status}`);
  }

  renderMusicAnalysis(payload);
  appendCaption("Transcription", payload.summary || "No transcription summary.");
  if (Array.isArray(payload.warnings)) {
    for (const warning of payload.warnings) {
      appendCaption("Warning", warning);
    }
  }
  setSessionStatus("Transcription ready.");
}
