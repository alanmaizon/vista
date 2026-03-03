import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js";
import {
  getAuth,
  signInAnonymously,
  signInWithEmailAndPassword,
} from "https://www.gstatic.com/firebasejs/11.4.0/firebase-auth.js";

const elements = {
  firebaseConfig: document.getElementById("firebase-config"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  signIn: document.getElementById("sign-in"),
  authStatus: document.getElementById("auth-status"),
  mode: document.getElementById("mode"),
  goal: document.getElementById("goal"),
  micToggle: document.getElementById("mic-toggle"),
  cameraToggle: document.getElementById("camera-toggle"),
  screenToggle: document.getElementById("screen-toggle"),
  snapshot: document.getElementById("snapshot"),
  transcribeOnce: document.getElementById("transcribe-once"),
  scoreLine: document.getElementById("score-line"),
  importScore: document.getElementById("import-score"),
  renderScore: document.getElementById("render-score"),
  comparePerformance: document.getElementById("compare-performance"),
  start: document.getElementById("start"),
  captureHint: document.getElementById("capture-hint"),
  cameraWarning: document.getElementById("camera-warning"),
  sessionStatus: document.getElementById("session-status"),
  captions: document.getElementById("captions"),
  summary: document.getElementById("summary"),
  musicAnalysis: document.getElementById("music-analysis"),
  scoreRender: document.getElementById("score-render"),
  scoreNoteStrip: document.getElementById("score-note-strip"),
  riskBadge: document.getElementById("risk-badge"),
  preview: document.getElementById("preview"),
};

const appState = {
  brand: document.body.dataset.brand || "Janey Mac",
  domain: (document.body.dataset.domain || "VISION").toUpperCase(),
  firebaseApp: null,
  auth: null,
  user: null,
  clientConfigLoaded: false,
  musicRuntimeLoaded: false,
  verovioAvailable: null,
  activeMusicScoreId: null,
  activeMusicNotes: [],
  highlightedScoreNoteIndexes: [],
  focusedScoreNoteIndex: null,
  assistantResponseReady: false,
  ws: null,
  sessionId: null,
  audioContext: null,
  captureSource: null,
  processor: null,
  monitorGain: null,
  micStream: null,
  micEnabled: true,
  camStream: null,
  cameraEnabled: false,
  screenStream: null,
  screenEnabled: false,
  videoTimer: null,
  playbackCursor: 0,
};

const skillHints = {
  REORIENT: "Where am I relative to the hallway or doorway?",
  HOLD_STEADY: "Help me hold the sign steady and readable.",
  FRAME_COACH: "Help me center the label so it is readable.",
  READ_TEXT: "Read this menu or sign.",
  NAV_FIND: "Find the exit sign.",
  QUEUE_AND_COUNTER: "Find the check-in queue.",
  SHOP_VERIFY: "Check whether this is the correct cereal box.",
  PRICE_AND_DEAL_CHECK: "Compare the price of these two items.",
  MONEY_HANDLING: "Identify this note and confirm my change.",
  OBJECT_LOCATE: "Find my keys on the table.",
  DEVICE_BUTTONS_AND_DIALS: "Help me find the off button on this appliance.",
  SOCIAL_CONTEXT: "Tell me who is nearby and where they are.",
  FACE_TO_SPEAKER: "Help me turn toward the person speaking.",
  FORM_FILL_HELP: "Help me complete this kiosk step.",
  MEDICATION_LABEL_READ: "Read one medication label at a time. Do not interpret dosing.",
  COOKING_ASSIST: "Help me read the recipe and identify ingredients.",
  STAIRS_ESCALATOR_ELEVATOR: "Help me assess this elevator or escalator safely.",
  TRAFFIC_CROSSING: "Locate the crossing button or sign.",
  MEDICATION_DOSING: "Medication dosing is blocked. Use MEDICATION_LABEL_READ for label text only.",
  SHEET_FRAME_COACH: "Help me frame one clear stave or measure group.",
  READ_SCORE: "Read this measure or staff line.",
  HEAR_PHRASE: "Identify the melody, interval, chord, or arpeggio I just played.",
  COMPARE_PERFORMANCE: "Compare what I played with the intended notes or rhythm.",
  EAR_TRAIN: "Give me one ear-training drill at a time.",
  GENERATE_EXAMPLE: "Generate one original musical example or exercise.",
};

const musicExpectedKinds = {
  HEAR_PHRASE: "AUTO",
  COMPARE_PERFORMANCE: "PHRASE",
  EAR_TRAIN: "INTERVAL",
};

const skillCaptureRules = {
  HOLD_STEADY: {
    requiresCamera: true,
    hint: "Point the camera at one target only. Hold it steady until the assistant says the frame is readable.",
  },
  FRAME_COACH: {
    requiresCamera: true,
    hint: "Show one label, sign, or object at a time. Center it, move closer, and keep it still for 2 seconds.",
  },
  READ_TEXT: {
    requiresCamera: true,
    hint: "Show one sign or label at a time. Move closer until the text fills about half the frame, then hold still.",
  },
  SHOP_VERIFY: {
    requiresCamera: true,
    hint: "Show one package at a time. If you need the price checked, show the price tag in a separate close frame.",
  },
  PRICE_AND_DEAL_CHECK: {
    requiresCamera: true,
    hint: "Show one item or one price tag at a time. Compare only after both prices have been captured clearly.",
  },
  MONEY_HANDLING: {
    requiresCamera: true,
    hint: "Use a plain background and show one note or coin at a time. Do not hold a pile in frame.",
  },
  OBJECT_LOCATE: {
    requiresCamera: true,
    hint: "Sweep one surface slowly, then stop when the target area is centered. Narrow the frame if the scene is cluttered.",
  },
  DEVICE_BUTTONS_AND_DIALS: {
    requiresCamera: true,
    hint: "Show one control panel or dial at a time. Move close enough that labels and indicators are easy to read.",
  },
  FORM_FILL_HELP: {
    requiresCamera: true,
    hint: "Show only the active field or button area. Center it, reduce glare, and hold steady before asking for help.",
  },
  MEDICATION_LABEL_READ: {
    requiresCamera: true,
    hint: "Show one medication item at a time. Start with the front label close-up. Do not compare two inhalers at once.",
  },
  SHEET_FRAME_COACH: {
    requiresCamera: true,
    hint: "Show one staff line or one short score excerpt at a time. Center it, flatten the page, and reduce glare before reading.",
  },
  READ_SCORE: {
    requiresCamera: true,
    hint: "Show one measure group or one short system at a time. Keep the notation close, centered, and steady before analysis.",
  },
};

function iconSvg(name) {
  const icons = {
    mic:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/><path d="M7 11.5a5 5 0 0 0 10 0" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="M12 16.5V21" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="M9 21h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/></svg>',
    camera:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 8.5h11A2.5 2.5 0 0 1 18 11v2A2.5 2.5 0 0 1 15.5 15.5h-11A2.5 2.5 0 0 1 2 13v-2a2.5 2.5 0 0 1 2.5-2.5Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/><path d="m18 10 4-2v8l-4-2" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/></svg>',
    screen:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 9v10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="m8.5 12 3.5-3.5L15.5 12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/><path d="M8 20h8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/></svg>',
    snapshot:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 7.5 9.3 5h5.4L16 7.5h2.5A2.5 2.5 0 0 1 21 10v6a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16v-6a2.5 2.5 0 0 1 2.5-2.5H8Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/><circle cx="12" cy="13" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
    start:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.5v11l8-5.5-8-5.5Z" fill="currentColor"/></svg>',
    confirm:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5.5 12.5 4 4 9-9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.1"/></svg>',
    stop:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2.1"/></svg>',
    analyze:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15.5V12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M8 18V9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M12 20V5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M16 17V8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M20 14V10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/></svg>',
  };
  return icons[name] || "";
}

function renderButton(button, { icon, label, iconOnly = false }) {
  button.innerHTML = iconOnly
    ? `<span class="button-icon" aria-hidden="true">${iconSvg(icon)}</span><span class="sr-only">${label}</span>`
    : `<span class="button-content"><span class="button-icon" aria-hidden="true">${iconSvg(icon)}</span><span class="button-label">${label}</span></span>`;
  button.setAttribute("aria-label", label);
  button.title = label;
}

function setAuthStatus(message) {
  elements.authStatus.textContent = message;
  console.info(`[${appState.brand}][Auth]`, message);
}

function setSessionStatus(message) {
  elements.sessionStatus.textContent = message;
  console.info(`[${appState.brand}][Status]`, message);
}

function setRiskBadge(mode) {
  elements.riskBadge.textContent = mode;
  elements.riskBadge.classList.remove("caution", "refuse");
  if (mode === "CAUTION") {
    elements.riskBadge.classList.add("caution");
  }
  if (mode === "REFUSE") {
    elements.riskBadge.classList.add("refuse");
  }
}

function setRunningState(isRunning) {
  elements.start.disabled = false;
  if (!isRunning) {
    appState.assistantResponseReady = false;
  }
  updatePrimaryActionButton();
  refreshMediaButtons();
}

function sessionRunning() {
  return Boolean(appState.ws && appState.ws.readyState === WebSocket.OPEN);
}

function hasVisualSourceEnabled() {
  return appState.cameraEnabled || appState.screenEnabled;
}

function setToggleButton(button, enabled, onLabel, offLabel, icon) {
  renderButton(button, {
    icon,
    label: enabled ? onLabel : offLabel,
    iconOnly: true,
  });
  button.classList.toggle("is-on", enabled);
}

function primaryActionState() {
  if (!sessionRunning()) {
    return "start";
  }
  return appState.assistantResponseReady ? "confirm" : "stop";
}

function updatePrimaryActionButton() {
  const state = primaryActionState();
  elements.start.classList.remove("primary", "accent", "danger");

  if (state === "confirm") {
    elements.start.classList.add("accent");
    renderButton(elements.start, { icon: "confirm", label: "Confirm step" });
    return;
  }
  if (state === "stop") {
    elements.start.classList.add("danger");
    renderButton(elements.start, { icon: "stop", label: "Stop session" });
    return;
  }

  elements.start.classList.add("primary");
  renderButton(elements.start, { icon: "start", label: "Start session" });
}

function refreshMediaButtons() {
  setToggleButton(elements.micToggle, appState.micEnabled, "Microphone on", "Microphone off", "mic");
  setToggleButton(elements.cameraToggle, appState.cameraEnabled, "Camera on", "Camera off", "camera");
  setToggleButton(elements.screenToggle, appState.screenEnabled, "Screen share on", "Screen share off", "screen");
  renderButton(elements.snapshot, { icon: "snapshot", label: "Capture screenshot", iconOnly: true });
  elements.snapshot.disabled = !sessionRunning() || !hasVisualSourceEnabled();
  if (elements.transcribeOnce) {
    renderButton(elements.transcribeOnce, { icon: "analyze", label: "Transcribe clip" });
    elements.transcribeOnce.disabled = sessionRunning();
  }
  if (elements.importScore) {
    renderButton(elements.importScore, { icon: "confirm", label: "Import score" });
    elements.importScore.disabled = sessionRunning();
  }
  if (elements.renderScore) {
    renderButton(elements.renderScore, { icon: "start", label: "Render notation" });
    elements.renderScore.disabled = sessionRunning() || !appState.activeMusicScoreId;
  }
  if (elements.comparePerformance) {
    renderButton(elements.comparePerformance, { icon: "analyze", label: "Compare take" });
    elements.comparePerformance.disabled =
      sessionRunning() || !appState.activeMusicScoreId || !appState.micEnabled;
  }
}

function markAssistantResponseReady() {
  if (appState.assistantResponseReady) {
    return;
  }
  appState.assistantResponseReady = true;
  updatePrimaryActionButton();
}

function appendCaption(label, text) {
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

function renderSummary(bullets) {
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

function renderMusicAnalysis(result) {
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

function renderImportedScore(result) {
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

function flattenNotesFromMeasures(measures) {
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

function renderScoreNoteStrip() {
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
      appendCaption("Score", `Focused note ${index + 1}: ${note.note_name}, duration ${note.duration_code}.`);
    });
    fragment.appendChild(button);
  });
  elements.scoreNoteStrip.appendChild(fragment);
}

function renderScoreSurface(result) {
  if (!elements.scoreRender) {
    return;
  }

  elements.scoreRender.innerHTML = "";
  if (!result || typeof result !== "object") {
    elements.scoreRender.textContent = "No rendered notation is available.";
    return;
  }

  if (typeof result.svg === "string" && result.svg.trim()) {
    elements.scoreRender.innerHTML = result.svg;
    return;
  }

  const fallback = document.createElement("pre");
  fallback.className = "score-render-fallback";
  fallback.textContent = result.musicxml || "No MusicXML fallback was returned.";
  elements.scoreRender.appendChild(fallback);
}

function renderPerformanceComparison(result) {
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

function updateGoalHint() {
  const hint = skillHints[elements.mode.value] || "Describe what you need help with.";
  elements.goal.placeholder = hint;
}

function getCaptureRule() {
  return skillCaptureRules[elements.mode.value] || null;
}

function selectedSkillNeedsVisualSource() {
  return Boolean(getCaptureRule()?.requiresCamera);
}

function updateCaptureGuidance() {
  const rule = getCaptureRule();
  if (rule) {
    elements.captureHint.textContent = rule.hint;
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

function parseFirebaseConfig() {
  const raw = elements.firebaseConfig.value.trim();
  if (!raw) {
    throw new Error("Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.");
  }
  return JSON.parse(raw);
}

async function loadClientConfig() {
  if (appState.clientConfigLoaded) {
    return;
  }
  appState.clientConfigLoaded = true;

  try {
    const response = await fetch("/api/client-config");
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (!payload || typeof payload !== "object") {
      return;
    }
    const firebaseConfig = payload.firebaseConfig;
    if (!firebaseConfig || typeof firebaseConfig !== "object") {
      return;
    }
    if (!elements.firebaseConfig.value.trim()) {
      elements.firebaseConfig.value = JSON.stringify(firebaseConfig, null, 2);
      setAuthStatus("Firebase config loaded. Click Sign In.");
    }
  } catch {
    // Leave manual paste as the fallback path.
  }
}

async function loadMusicRuntimeStatus() {
  if (appState.domain !== "MUSIC" || appState.musicRuntimeLoaded) {
    return;
  }
  appState.musicRuntimeLoaded = true;
  if (!elements.scoreRender) {
    return;
  }

  try {
    if (!appState.user) {
      return;
    }
    const idToken = await appState.user.getIdToken(true);
    const response = await fetch("/api/music/runtime", {
      headers: {
        Authorization: `Bearer ${idToken}`,
      },
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    appState.verovioAvailable = Boolean(payload?.verovio_available);
    if (!appState.activeMusicScoreId && !sessionRunning()) {
      elements.scoreRender.textContent = appState.verovioAvailable
        ? "Verovio is available. Render notation will return SVG when a score is loaded."
        : "Verovio is not installed on the backend yet. Render notation will use MusicXML fallback until it is added.";
    }
    if (payload?.verovio_detail) {
      console.info(`[${appState.brand}][Verovio]`, payload.verovio_detail);
    }
  } catch {
    // Keep the default render placeholder when runtime status cannot be loaded.
  }
}

async function ensureFirebase() {
  if (appState.auth) {
    return appState.auth;
  }
  const config = parseFirebaseConfig();
  appState.firebaseApp = getApps()[0] || initializeApp(config);
  appState.auth = getAuth(appState.firebaseApp);
  return appState.auth;
}

async function signIn() {
  await loadClientConfig();
  const auth = await ensureFirebase();
  const email = elements.email.value.trim();
  const password = elements.password.value;

  let credential;
  if (email && password) {
    credential = await signInWithEmailAndPassword(auth, email, password);
  } else {
    credential = await signInAnonymously(auth);
  }

  appState.user = credential.user;
  setAuthStatus(`Signed in as ${appState.user.email || appState.user.uid}`);
  await loadMusicRuntimeStatus();
}

function toBase64(uint8Array) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < uint8Array.length; index += chunkSize) {
    const slice = uint8Array.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

function fromBase64(base64Value) {
  const binary = atob(base64Value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function downsampleBuffer(buffer, inputRate, outputRate) {
  if (outputRate >= inputRate) {
    return buffer;
  }
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const output = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < output.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let index = offsetBuffer; index < nextOffsetBuffer && index < buffer.length; index += 1) {
      accum += buffer[index];
      count += 1;
    }
    output[offsetResult] = count ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }

  return output;
}

function floatToPcm16Bytes(floatBuffer) {
  const output = new Int16Array(floatBuffer.length);
  for (let index = 0; index < floatBuffer.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[index]));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return new Uint8Array(output.buffer);
}

async function ensureAudioContext() {
  if (!appState.audioContext) {
    appState.audioContext = new AudioContext({ latencyHint: "interactive" });
  }
  if (appState.audioContext.state === "suspended") {
    await appState.audioContext.resume();
  }
  return appState.audioContext;
}

function queuePlaybackChunk(base64Data, mime = "audio/pcm;rate=24000") {
  if (!appState.audioContext) {
    return;
  }
  if (typeof mime !== "string" || !mime.toLowerCase().startsWith("audio/pcm")) {
    appendCaption("Audio", `Received unsupported audio format: ${mime || "unknown"}`);
    return;
  }

  const bytes = fromBase64(base64Data);
  const frameCount = Math.floor(bytes.byteLength / 2);
  if (!frameCount) {
    return;
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, frameCount * 2);
  const samples = new Float32Array(frameCount);
  for (let index = 0; index < frameCount; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 0x8000;
  }

  const audioBuffer = appState.audioContext.createBuffer(1, samples.length, 24000);
  audioBuffer.copyToChannel(samples, 0);

  const source = appState.audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(appState.audioContext.destination);

  const startAt = Math.max(appState.audioContext.currentTime, appState.playbackCursor);
  source.start(startAt);
  appState.playbackCursor = startAt + audioBuffer.duration;
}

function concatUint8Arrays(chunks) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

async function captureOneShotPcmClip({ durationMs = 2400 } = {}) {
  await ensureAudioContext();

  const tempStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  });

  const source = appState.audioContext.createMediaStreamSource(tempStream);
  const processor = appState.audioContext.createScriptProcessor(4096, 1, 1);
  const sink = appState.audioContext.createGain();
  sink.gain.value = 0;
  const chunks = [];

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      processor.disconnect();
      processor.onaudioprocess = null;
      source.disconnect();
      sink.disconnect();
      for (const track of tempStream.getTracks()) {
        track.stop();
      }
    };

    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      const downsampled = downsampleBuffer(input, appState.audioContext.sampleRate, 16000);
      chunks.push(floatToPcm16Bytes(downsampled));
    };

    source.connect(processor);
    processor.connect(sink);
    sink.connect(appState.audioContext.destination);

    window.setTimeout(() => {
      try {
        cleanup();
        resolve(concatUint8Arrays(chunks));
      } catch (error) {
        reject(error);
      }
    }, durationMs);
  });
}

async function transcribeOneShotClip() {
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

  const payload = await response.json();
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

async function importScoreLine() {
  if (sessionRunning()) {
    throw new Error("Stop the live session before importing a score.");
  }
  if (!appState.user) {
    throw new Error("Sign in before importing a score.");
  }

  const sourceText = elements.scoreLine?.value.trim() || "";
  if (!sourceText) {
    throw new Error("Enter a score line before importing.");
  }

  setSessionStatus("Importing score...");
  const idToken = await appState.user.getIdToken(true);
  const response = await fetch("/api/music/score/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      source_text: sourceText,
      source_format: "NOTE_LINE",
      time_signature: "4/4",
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Score import failed with ${response.status}`);
  }

  appState.activeMusicScoreId = payload.score_id || null;
  appState.activeMusicNotes = flattenNotesFromMeasures(payload.measures);
  appState.highlightedScoreNoteIndexes = [];
  appState.focusedScoreNoteIndex = null;
  renderImportedScore(payload);
  renderScoreSurface(null);
  renderScoreNoteStrip();
  refreshMediaButtons();
  appendCaption("Score", payload.summary || "Score import complete.");
  if (Array.isArray(payload.warnings)) {
    for (const warning of payload.warnings) {
      appendCaption("Warning", warning);
    }
  }
  setSessionStatus("Score import ready.");
}

async function renderStoredScore() {
  if (sessionRunning()) {
    throw new Error("Stop the live session before rendering notation.");
  }
  if (!appState.user) {
    throw new Error("Sign in before rendering notation.");
  }
  if (!appState.activeMusicScoreId) {
    throw new Error("Import a score before rendering notation.");
  }

  setSessionStatus("Rendering notation...");
  const idToken = await appState.user.getIdToken(true);
  const response = await fetch(`/api/music/score/${appState.activeMusicScoreId}/render`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Render failed with ${response.status}`);
  }

  appState.activeMusicNotes = Array.isArray(payload.expected_notes) ? payload.expected_notes : appState.activeMusicNotes;
  appState.highlightedScoreNoteIndexes = [];
  appState.focusedScoreNoteIndex = null;
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
}

async function comparePerformanceClip() {
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
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Comparison failed with ${response.status}`);
  }

  appState.activeMusicNotes = Array.isArray(payload.expected_notes) ? payload.expected_notes : appState.activeMusicNotes;
  appState.highlightedScoreNoteIndexes = payload.needs_replay
    ? []
    : Array.isArray(payload.comparisons)
      ? payload.comparisons
          .filter((item) => !item.pitch_match || !item.rhythm_match)
          .map((item) => Math.max(0, Number(item.index || 1) - 1))
      : [];
  appState.focusedScoreNoteIndex = appState.highlightedScoreNoteIndexes[0] ?? null;
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
  setSessionStatus(payload.needs_replay ? "Replay requested." : "Comparison ready.");
}

async function createSession(idToken) {
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      domain: appState.domain,
      mode: elements.mode.value,
      goal: elements.goal.value.trim() || null,
    }),
  });

  if (!response.ok) {
    throw new Error(`Session create failed with ${response.status}`);
  }

  return response.json();
}

function createLiveSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${protocol}://${window.location.host}/ws/live`);
}

function waitForSocketOpen(ws) {
  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener("error", () => reject(new Error("WebSocket connection failed")), {
      once: true,
    });
  });
}

async function enableMicCapture() {
  if (!appState.micEnabled || !sessionRunning() || appState.micStream) {
    return;
  }

  await ensureAudioContext();

  appState.micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  });

  appState.captureSource = appState.audioContext.createMediaStreamSource(appState.micStream);
  appState.processor = appState.audioContext.createScriptProcessor(4096, 1, 1);
  appState.monitorGain = appState.audioContext.createGain();
  appState.monitorGain.gain.value = 0;

  appState.processor.onaudioprocess = (event) => {
    if (!sessionRunning()) {
      return;
    }
    const input = event.inputBuffer.getChannelData(0);
    const downsampled = downsampleBuffer(input, appState.audioContext.sampleRate, 16000);
    const payload = floatToPcm16Bytes(downsampled);
    appState.ws.send(
      JSON.stringify({
        type: "client.audio",
        mime: "audio/pcm;rate=16000",
        data_b64: toBase64(payload),
      })
    );
  };

  appState.captureSource.connect(appState.processor);
  appState.processor.connect(appState.monitorGain);
  appState.monitorGain.connect(appState.audioContext.destination);
}

async function disableMicCapture() {
  if (appState.processor) {
    appState.processor.disconnect();
    appState.processor.onaudioprocess = null;
    appState.processor = null;
  }

  if (appState.captureSource) {
    appState.captureSource.disconnect();
    appState.captureSource = null;
  }

  if (appState.monitorGain) {
    appState.monitorGain.disconnect();
    appState.monitorGain = null;
  }

  if (appState.micStream) {
    for (const track of appState.micStream.getTracks()) {
      track.stop();
    }
    appState.micStream = null;
  }
}

function updatePreviewSource() {
  if (appState.screenStream) {
    elements.preview.srcObject = appState.screenStream;
    return;
  }
  if (appState.camStream) {
    elements.preview.srcObject = appState.camStream;
    return;
  }
  elements.preview.srcObject = null;
}

async function ensureCameraCapture() {
  if (!appState.cameraEnabled || !sessionRunning() || appState.camStream) {
    return;
  }
  appState.camStream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: { ideal: "environment" },
      width: { ideal: 1280 },
      height: { ideal: 720 },
    },
    audio: false,
  });
  updatePreviewSource();
}

async function ensureScreenCapture() {
  if (!appState.screenEnabled || !sessionRunning() || appState.screenStream) {
    return;
  }
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error("Screen sharing is not supported in this browser.");
  }

  appState.screenStream = await navigator.mediaDevices.getDisplayMedia({
    video: {
      frameRate: { ideal: 5, max: 8 },
    },
    audio: false,
  });

  const [track] = appState.screenStream.getVideoTracks();
  if (track) {
    track.addEventListener("ended", () => {
      appState.screenEnabled = false;
      void stopScreenCapture();
      updateCaptureGuidance();
      refreshMediaButtons();
      appendCaption("Status", "Screen sharing stopped.");
    });
  }

  updatePreviewSource();
}

async function stopCameraCapture() {
  if (appState.camStream) {
    for (const track of appState.camStream.getTracks()) {
      track.stop();
    }
    appState.camStream = null;
  }
  updatePreviewSource();
}

async function stopScreenCapture() {
  if (appState.screenStream) {
    for (const track of appState.screenStream.getTracks()) {
      track.stop();
    }
    appState.screenStream = null;
  }
  updatePreviewSource();
  restartVisualFrameTimer();
}

function capturePreviewFrame() {
  const video = elements.preview;
  if (!video.srcObject || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    return null;
  }

  const width = video.videoWidth || 1280;
  const height = video.videoHeight || 720;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }
  context.drawImage(video, 0, 0, width, height);

  const dataUrl = canvas.toDataURL("image/jpeg", 0.72);
  return dataUrl.split(",", 2)[1] || null;
}

function sendVisualFrame(base64Data) {
  if (!sessionRunning()) {
    return;
  }
  appState.ws.send(
    JSON.stringify({
      type: "client.video",
      mime: "image/jpeg",
      data_b64: base64Data,
    })
  );
}

function restartVisualFrameTimer() {
  if (appState.videoTimer) {
    clearInterval(appState.videoTimer);
    appState.videoTimer = null;
  }

  if (!sessionRunning() || !hasVisualSourceEnabled()) {
    return;
  }

  appState.videoTimer = window.setInterval(() => {
    const base64Data = capturePreviewFrame();
    if (!base64Data) {
      return;
    }
    sendVisualFrame(base64Data);
  }, 1000);
}

async function syncVisualCapture() {
  if (!sessionRunning()) {
    return;
  }

  if (appState.screenEnabled) {
    await ensureScreenCapture();
    await stopCameraCapture();
  } else {
    await stopScreenCapture();
    if (appState.cameraEnabled) {
      await ensureCameraCapture();
    } else {
      await stopCameraCapture();
    }
  }

  updatePreviewSource();
  restartVisualFrameTimer();
}

async function captureScreenshot() {
  if (!sessionRunning()) {
    appendCaption("Status", "Start a live session before capturing a screenshot.");
    return;
  }
  if (!hasVisualSourceEnabled()) {
    appendCaption("Status", "Turn on camera or screen sharing before capturing a screenshot.");
    return;
  }
  const base64Data = capturePreviewFrame();
  if (!base64Data) {
    appendCaption("Status", "Wait for the live preview to appear before capturing a screenshot.");
    return;
  }
  sendVisualFrame(base64Data);
  appendCaption("Setup", "Captured one still frame for analysis.");
}

async function stopMedia() {
  if (appState.videoTimer) {
    clearInterval(appState.videoTimer);
    appState.videoTimer = null;
  }

  await disableMicCapture();
  await stopScreenCapture();
  await stopCameraCapture();
}

async function stopSession({ notifyServer = true } = {}) {
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

function attachSocketHandlers(ws) {
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
        markAssistantResponseReady();
        appendCaption("Live", payload.text);
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

  ws.onclose = async () => {
    await stopMedia();
    appState.ws = null;
    appState.sessionId = null;
    setRunningState(false);
    refreshMediaButtons();
  };
}

async function startSession() {
  if (!appState.user) {
    throw new Error("Sign in before starting a session.");
  }
  if (!appState.micEnabled && !hasVisualSourceEnabled()) {
    throw new Error("Turn on mic, camera, or screen sharing before starting.");
  }
  if (selectedSkillNeedsVisualSource() && !hasVisualSourceEnabled()) {
    throw new Error("Turn on camera or screen sharing for this skill, then show one item or panel at a time.");
  }

  elements.summary.innerHTML = "";
  appState.playbackCursor = 0;
  appState.assistantResponseReady = false;
  setRiskBadge("NORMAL");
  setSessionStatus("Creating session...");

  const idToken = await appState.user.getIdToken(true);
  const session = await createSession(idToken);
  appState.sessionId = session.id;

  setSessionStatus("Opening live websocket...");
  appState.ws = createLiveSocket();
  attachSocketHandlers(appState.ws);
  await waitForSocketOpen(appState.ws);
  appState.ws.send(
    JSON.stringify({
      type: "client.init",
      token: idToken,
      session_id: session.id,
      mode: elements.mode.value,
    })
  );

  if (appState.micEnabled) {
    await enableMicCapture();
  }
  await syncVisualCapture();

  const captureRule = getCaptureRule();
  if (captureRule) {
    appendCaption("Setup", captureRule.hint);
  } else if (!hasVisualSourceEnabled()) {
    appendCaption("Setup", "Audio-only mode is active. Use a short spoken question.");
  }
  if (appState.screenEnabled) {
    appendCaption("Setup", "Screen sharing is active. Use Capture Screenshot for an extra still frame.");
  }

  setRunningState(true);
  setSessionStatus("Live session running.");
}

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
      appState.ws.send(JSON.stringify({ type: "client.confirm" }));
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
        await enableMicCapture();
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

if (elements.transcribeOnce) {
  elements.transcribeOnce.addEventListener("click", async () => {
    try {
      await transcribeOneShotClip();
    } catch (error) {
      appendCaption("Error", error.message || "Unable to transcribe the clip.");
      setSessionStatus("Transcription failed.");
    }
  });
}

if (elements.importScore) {
  elements.importScore.addEventListener("click", async () => {
    try {
      await importScoreLine();
    } catch (error) {
      appendCaption("Error", error.message || "Unable to import the score.");
      setSessionStatus("Score import failed.");
    }
  });
}

if (elements.renderScore) {
  elements.renderScore.addEventListener("click", async () => {
    try {
      await renderStoredScore();
    } catch (error) {
      appendCaption("Error", error.message || "Unable to render notation.");
      setSessionStatus("Render failed.");
    }
  });
}

if (elements.comparePerformance) {
  elements.comparePerformance.addEventListener("click", async () => {
    try {
      await comparePerformanceClip();
    } catch (error) {
      appendCaption("Error", error.message || "Unable to compare this take.");
      setSessionStatus("Comparison failed.");
    }
  });
}

elements.mode.addEventListener("change", () => {
  updateGoalHint();
  updateCaptureGuidance();
});
updateGoalHint();
updateCaptureGuidance();
updatePrimaryActionButton();
refreshMediaButtons();
renderScoreNoteStrip();
void loadClientConfig();
