import { appState, elements } from "./state.js";
import { appendCaption } from "./ui.js";

export function renderSummary(bullets) {
  elements.summary.innerHTML = "";
  for (const bullet of bullets) {
    const li = document.createElement("li");
    li.textContent = bullet;
    elements.summary.appendChild(li);
  }
  if (bullets.length) {
    console.groupCollapsed(`[${appState.brand}] Session summary`);
    for (const bullet of bullets) {
      console.info(bullet);
    }
    console.groupEnd();
  }
}

export function renderMusicAnalysis(result) {
  if (!elements.musicAnalysis) {
    return;
  }

  if (!result || typeof result !== "object") {
    elements.musicAnalysis.textContent = "No transcription result.";
    return;
  }

  const lines = [
    result.summary || "No transcription summary.",
  ];
  if (Array.isArray(result.notes) && result.notes.length) {
    lines.push(`Notes: ${result.notes.map((note) => note.note_name).join(", ")}`);
  }
  if (result.interval_hint) {
    lines.push(`Interval: ${result.interval_hint}`);
  }
  if (result.harmony_hint) {
    lines.push(`Harmony: ${result.harmony_hint}`);
  }
  if (Array.isArray(result.warnings) && result.warnings.length) {
    lines.push(`Warnings: ${result.warnings.join(" ")}`);
  }
  elements.musicAnalysis.textContent = lines.join(" ");
}

export function renderImportedScore(result) {
  if (!elements.musicAnalysis) {
    return;
  }

  if (!result || typeof result !== "object") {
    elements.musicAnalysis.textContent = "No score import result.";
    return;
  }

  const lines = [
    result.summary || "Score import complete.",
  ];
  if (typeof result.normalized === "string" && result.normalized) {
    lines.push(`Normalized: ${result.normalized}`);
  }
  if (result.score_id) {
    lines.push(`Saved score: ${result.score_id}`);
  }
  if (Array.isArray(result.measures) && result.measures.length) {
    const measureSummary = result.measures
      .map((measure) => {
        const noteNames = Array.isArray(measure.notes)
          ? measure.notes.map((note) => note.note_name).join(", ")
          : "";
        return `Bar ${measure.index}: ${noteNames || "no notes"} (${measure.total_beats} beats)`;
      })
      .join(" | ");
    lines.push(measureSummary);
  }
  if (Array.isArray(result.warnings) && result.warnings.length) {
    lines.push(`Warnings: ${result.warnings.join(" ")}`);
  }
  elements.musicAnalysis.textContent = lines.join(" ");
}

export function flattenNotesFromMeasures(measures) {
  if (!Array.isArray(measures)) {
    return [];
  }
  const notes = [];
  for (const measure of measures) {
    if (!Array.isArray(measure?.notes)) {
      continue;
    }
    for (const note of measure.notes) {
      notes.push(note);
    }
  }
  return notes;
}

export function renderScoreNoteStrip() {
  if (!elements.scoreNoteStrip) {
    return;
  }

  elements.scoreNoteStrip.innerHTML = "";
  if (!Array.isArray(appState.activeMusicNotes) || !appState.activeMusicNotes.length) {
    elements.scoreNoteStrip.textContent = "Imported and rendered score notes will appear here for focused practice.";
    return;
  }

  const fragment = document.createDocumentFragment();
  appState.activeMusicNotes.forEach((note, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "score-note-pill";
    button.textContent = `${note.note_name}`;
    if (index === appState.focusedScoreNoteIndex) {
      button.classList.add("is-focused");
    }
    if (appState.highlightedScoreNoteIndexes.includes(index)) {
      button.classList.add("is-highlighted");
    }
    button.title = `${note.note_name} (${note.duration_code})`;
    button.addEventListener("click", () => {
      appState.focusedScoreNoteIndex = index;
      renderScoreNoteStrip();
      renderScoreOverlay();
      appendCaption("Score", `Focused note ${index + 1}: ${note.note_name}, duration ${note.duration_code}.`);
    });
    fragment.appendChild(button);
  });
  elements.scoreNoteStrip.appendChild(fragment);
}

export function setScoreOverlayState({ mode = "idle", summary = "", markers = [] } = {}) {
  appState.scoreOverlayMode = mode;
  appState.scoreOverlaySummary = summary;
  appState.scoreOverlayMarkers = Array.isArray(markers) ? markers : [];
  renderScoreOverlay();
}

export function buildScoreOverlayMarkersForState(mode, comparisons = []) {
  const noteCount = Array.isArray(appState.activeMusicNotes) ? appState.activeMusicNotes.length : 0;
  if (!noteCount) {
    return [];
  }
  if (mode === "replay") {
    return Array.from({ length: noteCount }, () => ({ state: "replay" }));
  }
  if (!Array.isArray(comparisons) || !comparisons.length) {
    return Array.from({ length: noteCount }, () => ({ state: "neutral" }));
  }
  return comparisons.slice(0, noteCount).map((item) => {
    if (!item?.pitch_match) {
      return { state: "pitch" };
    }
    if (!item?.rhythm_match) {
      return { state: "rhythm" };
    }
    return { state: "match" };
  });
}

export function normalizeGlyphAnchorPercent(value) {
  if (!Number.isFinite(value)) {
    return null;
  }
  return Math.max(0, Math.min(100, value));
}

export function diatonicStepFromNoteName(noteName) {
  const match = typeof noteName === "string" ? noteName.match(/^([A-Ga-g])([#b]?)(-?\d+)$/) : null;
  if (!match) {
    return null;
  }
  const letter = match[1].toUpperCase();
  const octave = Number(match[3]);
  if (!Number.isFinite(octave)) {
    return null;
  }
  const diatonicOffsets = {
    C: 0,
    D: 1,
    E: 2,
    F: 3,
    G: 4,
    A: 5,
    B: 6,
  };
  return octave * 7 + diatonicOffsets[letter];
}

export function fallbackStaffTopForNoteIndex(index) {
  const note = Array.isArray(appState.activeMusicNotes) ? appState.activeMusicNotes[index] : null;
  const step = diatonicStepFromNoteName(note?.note_name);
  if (!Number.isFinite(step)) {
    return 50;
  }

  const lowestStaffStep = diatonicStepFromNoteName("E4");
  const highestStaffStep = diatonicStepFromNoteName("F5");
  if (!Number.isFinite(lowestStaffStep) || !Number.isFinite(highestStaffStep) || lowestStaffStep === highestStaffStep) {
    return 50;
  }

  const normalized = (step - highestStaffStep) / (lowestStaffStep - highestStaffStep);
  const clamped = Math.max(-0.3, Math.min(1.3, normalized));
  return 20 + clamped * 60;
}

export function normalizeScoreLayoutHints(layoutHints) {
  if (!Array.isArray(layoutHints)) {
    return [];
  }
  return layoutHints
    .map((item, index) => {
      const left = normalizeGlyphAnchorPercent(Number(item?.left_pct));
      const top = normalizeGlyphAnchorPercent(Number(item?.top_pct));
      if (left === null || top === null) {
        return null;
      }
      return {
        index: Number.isFinite(Number(item?.index)) ? Number(item.index) : index,
        left,
        top,
      };
    })
    .filter(Boolean);
}

export function glyphAnchorRect(node) {
  if (!(node instanceof Element)) {
    return null;
  }
  const preferred = node.querySelector(
    ".notehead, [class~='notehead'], [class*='notehead']"
  );
  const target = preferred || node;
  const rect = target.getBoundingClientRect();
  if (!rect.width && !rect.height) {
    return null;
  }
  return rect;
}

export function collectScoreGlyphAnchors() {
  if (!elements.scoreRender) {
    return [];
  }
  const noteCount = Array.isArray(appState.activeMusicNotes) ? appState.activeMusicNotes.length : 0;
  if (!noteCount) {
    return [];
  }

  const scoreStage = elements.scoreRender.closest(".score-stage");
  const svg = elements.scoreRender.querySelector("svg");
  if (!scoreStage || !svg) {
    return [];
  }

  const stageRect = scoreStage.getBoundingClientRect();
  if (!stageRect.width || !stageRect.height) {
    return [];
  }

  let candidates = Array.from(svg.querySelectorAll("g.note"));
  if (!candidates.length) {
    candidates = Array.from(
      svg.querySelectorAll("g[class~='note'], g[class^='note'], g[class*=' note']")
    );
  }
  if (!candidates.length) {
    candidates = Array.from(svg.querySelectorAll(".notehead, [class~='notehead']"));
  }
  if (!candidates.length) {
    return [];
  }

  const seen = new Set();
  const anchors = [];
  for (const candidate of candidates) {
    if (seen.has(candidate)) {
      continue;
    }
    seen.add(candidate);
    const rect = glyphAnchorRect(candidate);
    if (!rect) {
      continue;
    }
    const left = normalizeGlyphAnchorPercent(
      ((rect.left + rect.width / 2) - stageRect.left) / stageRect.width * 100
    );
    const top = normalizeGlyphAnchorPercent(
      ((rect.top + rect.height / 2) - stageRect.top) / stageRect.height * 100
    );
    if (left === null || top === null) {
      continue;
    }
    anchors.push({ left, top });
    if (anchors.length >= noteCount) {
      break;
    }
  }

  return anchors;
}

export function renderScoreOverlay() {
  if (!elements.scoreOverlay) {
    return;
  }

  elements.scoreOverlay.innerHTML = "";
  const noteCount = Array.isArray(appState.activeMusicNotes) ? appState.activeMusicNotes.length : 0;
  if (!noteCount || appState.scoreOverlayMode === "idle") {
    elements.scoreOverlay.classList.add("is-hidden");
    return;
  }

  elements.scoreOverlay.classList.remove("is-hidden");

  const badge = document.createElement("div");
  badge.className = "score-overlay-badge";

  if (appState.scoreOverlayMode === "replay") {
    badge.textContent = "Replay required";
    badge.classList.add("is-replay");
  } else if (appState.scoreOverlayMode === "match") {
    badge.textContent = "Strong match";
    badge.classList.add("is-match");
  } else if (appState.scoreOverlayMode === "difference") {
    badge.textContent = "Differences highlighted";
    badge.classList.add("is-difference");
  } else {
    badge.textContent = appState.scoreOverlaySummary || "Score ready";
  }
  elements.scoreOverlay.appendChild(badge);

  const track = document.createElement("div");
  track.className = "score-overlay-track";

  const staff = document.createElement("div");
  staff.className = "score-overlay-staff";
  for (let index = 0; index < 5; index += 1) {
    const line = document.createElement("div");
    line.className = "score-overlay-staff-line";
    line.style.top = `${index * 25}%`;
    staff.appendChild(line);
  }
  track.appendChild(staff);

  const markers = appState.scoreOverlayMarkers.length
    ? appState.scoreOverlayMarkers
    : buildScoreOverlayMarkersForState(appState.scoreOverlayMode);
  const backendAnchors =
    Array.isArray(appState.scoreLayoutHints) && appState.scoreLayoutHints.length >= noteCount
      ? appState.scoreLayoutHints.slice(0, noteCount).map((anchor) => ({
          left: anchor.left,
          top: anchor.top,
        }))
      : null;
  const glyphAnchors =
    Array.isArray(appState.scoreGlyphAnchors) && appState.scoreGlyphAnchors.length >= noteCount
      ? appState.scoreGlyphAnchors.slice(0, noteCount)
      : null;
  const anchoredMarkers = backendAnchors || glyphAnchors;

  if (anchoredMarkers) {
    markers.forEach((marker, index) => {
      const anchor = anchoredMarkers[index];
      const markerNode = document.createElement("div");
      markerNode.className = "score-overlay-marker is-anchored";
      markerNode.classList.add(`is-${marker.state || "neutral"}`);
      if (index === appState.focusedScoreNoteIndex) {
        markerNode.classList.add("is-focused");
      }
      markerNode.style.left = `${anchor.left}%`;
      markerNode.style.top = `${anchor.top}%`;
      elements.scoreOverlay.appendChild(markerNode);
    });
    return;
  }

  markers.forEach((marker, index) => {
    const markerNode = document.createElement("div");
    markerNode.className = "score-overlay-marker";
    markerNode.classList.add(`is-${marker.state || "neutral"}`);
    if (index === appState.focusedScoreNoteIndex) {
      markerNode.classList.add("is-focused");
    }
    const percent = noteCount === 1 ? 50 : (index / (noteCount - 1)) * 100;
    markerNode.style.left = `${percent}%`;
    markerNode.style.top = `${fallbackStaffTopForNoteIndex(index)}%`;
    track.appendChild(markerNode);
  });

  elements.scoreOverlay.appendChild(track);
}

export function renderScoreSurface(result) {
  if (!elements.scoreRender) {
    return;
  }

  elements.scoreRender.innerHTML = "";
  appState.scoreLayoutHints = normalizeScoreLayoutHints(result?.note_layout);
  appState.scoreGlyphAnchors = [];
  if (!result || typeof result !== "object") {
    elements.scoreRender.textContent = "No rendered notation is available.";
    return;
  }

  if (typeof result.svg === "string" && result.svg.trim()) {
    elements.scoreRender.innerHTML = result.svg;
    window.requestAnimationFrame(() => {
      appState.scoreGlyphAnchors = collectScoreGlyphAnchors();
      renderScoreOverlay();
    });
    return;
  }

  const fallback = document.createElement("pre");
  fallback.className = "score-render-fallback";
  fallback.textContent = result.musicxml || "No MusicXML fallback was returned.";
  elements.scoreRender.appendChild(fallback);
  renderScoreOverlay();
}

export function renderPerformanceComparison(result) {
  if (!elements.musicAnalysis) {
    return;
  }

  if (!result || typeof result !== "object") {
    elements.musicAnalysis.textContent = "No comparison result.";
    return;
  }

  const lines = [
    result.summary || "No comparison summary.",
  ];
  if (result.needs_replay) {
    lines.push("Replay requested before treating this take as reliable.");
  }
  if (Array.isArray(result.mismatches) && result.mismatches.length) {
    lines.push(`Differences: ${result.mismatches.join(" ")}`);
  }
  if (result.played_phrase?.notes?.length) {
    lines.push(
      `Played: ${result.played_phrase.notes.map((note) => note.note_name).join(", ")}`
    );
  }
  if (Array.isArray(result.expected_notes) && result.expected_notes.length) {
    lines.push(
      `Expected: ${result.expected_notes.map((note) => note.note_name).join(", ")}`
    );
  }
  lines.push(`Accuracy: ${Math.round((Number(result.accuracy) || 0) * 100)}%.`);
  elements.musicAnalysis.textContent = lines.join(" ");
}

export function activeMeasureCount() {
  return Array.isArray(appState.activeMusicMeasures) ? appState.activeMusicMeasures.length : 0;
}

export function noteOffsetForMeasure(measureIndex) {
  if (!Array.isArray(appState.activeMusicMeasures) || measureIndex <= 0) {
    return 0;
  }
  let offset = 0;
  for (let index = 0; index < measureIndex - 1; index += 1) {
    const measure = appState.activeMusicMeasures[index];
    offset += Array.isArray(measure?.notes) ? measure.notes.length : 0;
  }
  return offset;
}

export function noteRangeForMeasure(measureIndex) {
  if (!Array.isArray(appState.activeMusicMeasures) || measureIndex <= 0) {
    return { start: 0, end: 0 };
  }
  const start = noteOffsetForMeasure(measureIndex);
  const count = Array.isArray(appState.activeMusicMeasures[measureIndex - 1]?.notes)
    ? appState.activeMusicMeasures[measureIndex - 1].notes.length
    : 0;
  return { start, end: start + count };
}

export function focusLessonMeasure(measureIndex, explicitRange = null) {
  if (measureIndex <= 0) {
    return;
  }
  const range = explicitRange && Number.isInteger(explicitRange.start) && Number.isInteger(explicitRange.end)
    ? explicitRange
    : noteRangeForMeasure(measureIndex);
  appState.highlightedScoreNoteIndexes = Array.from(
    { length: Math.max(0, range.end - range.start) },
    (_, offset) => range.start + offset
  );
  appState.focusedScoreNoteIndex = appState.highlightedScoreNoteIndexes[0] ?? null;
  setScoreOverlayState({
    mode: "score-ready",
    summary: `Focus on bar ${measureIndex}.`,
    markers: buildScoreOverlayMarkersForState("score-ready"),
  });
  renderScoreNoteStrip();
}

export function usesDeterministicLivePhraseCapture(modeOverride = elements.mode.value) {
  return appState.domain === "MUSIC" && modeOverride === "HEAR_PHRASE";
}
