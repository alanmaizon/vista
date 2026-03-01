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
  useCamera: document.getElementById("use-camera"),
  start: document.getElementById("start"),
  confirm: document.getElementById("confirm"),
  stop: document.getElementById("stop"),
  sessionStatus: document.getElementById("session-status"),
  captions: document.getElementById("captions"),
  summary: document.getElementById("summary"),
  riskBadge: document.getElementById("risk-badge"),
  preview: document.getElementById("preview"),
};

const appState = {
  firebaseApp: null,
  auth: null,
  user: null,
  clientConfigLoaded: false,
  ws: null,
  sessionId: null,
  audioContext: null,
  captureSource: null,
  processor: null,
  monitorGain: null,
  micStream: null,
  camStream: null,
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
  COOKING_ASSIST: "Help me read the recipe and identify ingredients.",
  STAIRS_ESCALATOR_ELEVATOR: "Help me assess this elevator or escalator safely.",
  TRAFFIC_CROSSING: "Locate the crossing button or sign.",
  MEDICATION_DOSING: "Read the prescription label text only.",
};

function setAuthStatus(message) {
  elements.authStatus.textContent = message;
}

function setSessionStatus(message) {
  elements.sessionStatus.textContent = message;
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
  elements.start.disabled = isRunning;
  elements.confirm.disabled = !isRunning;
  elements.stop.disabled = !isRunning;
}

function appendCaption(label, text) {
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
}

function updateGoalHint() {
  const hint = skillHints[elements.mode.value] || "Describe what you need help with.";
  elements.goal.placeholder = hint;
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

function queuePlaybackChunk(base64Data) {
  if (!appState.audioContext) {
    return;
  }

  const bytes = fromBase64(base64Data);
  const pcm16 = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
  const samples = new Float32Array(pcm16.length);
  for (let index = 0; index < pcm16.length; index += 1) {
    samples[index] = pcm16[index] / 0x8000;
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

async function createSession(idToken) {
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      mode: elements.mode.value,
      goal: elements.goal.value.trim() || null,
    }),
  });

  if (!response.ok) {
    throw new Error(`Session create failed with ${response.status}`);
  }

  return response.json();
}

function createLiveSocket(idToken, sessionId) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = new URL(`${protocol}://${window.location.host}/ws/live`);
  url.searchParams.set("token", idToken);
  url.searchParams.set("session_id", sessionId);
  url.searchParams.set("mode", elements.mode.value);
  return new WebSocket(url);
}

function waitForSocketOpen(ws) {
  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener("error", () => reject(new Error("WebSocket connection failed")), {
      once: true,
    });
  });
}

async function startAudioCapture() {
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
    if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
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

async function startVideoCapture() {
  if (!elements.useCamera.checked) {
    elements.preview.srcObject = null;
    return;
  }

  appState.camStream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: { ideal: "environment" },
      width: { ideal: 960 },
      height: { ideal: 720 },
    },
    audio: false,
  });

  elements.preview.srcObject = appState.camStream;

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Unable to capture camera frames in this browser.");
  }

  appState.videoTimer = window.setInterval(() => {
    if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN || !appState.camStream) {
      return;
    }

    const track = appState.camStream.getVideoTracks()[0];
    if (!track) {
      return;
    }

    const settings = track.getSettings();
    canvas.width = Number(settings.width) || 640;
    canvas.height = Number(settings.height) || 480;
    context.drawImage(elements.preview, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.68);
    const base64Data = dataUrl.split(",", 2)[1];

    appState.ws.send(
      JSON.stringify({
        type: "client.video",
        mime: "image/jpeg",
        data_b64: base64Data,
      })
    );
  }, 1000);
}

async function stopMedia() {
  if (appState.videoTimer) {
    clearInterval(appState.videoTimer);
    appState.videoTimer = null;
  }

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

  if (appState.camStream) {
    for (const track of appState.camStream.getTracks()) {
      track.stop();
    }
    appState.camStream = null;
  }

  elements.preview.srcObject = null;
}

async function stopSession({ notifyServer = true } = {}) {
  if (notifyServer && appState.ws && appState.ws.readyState === WebSocket.OPEN) {
    appState.ws.send(JSON.stringify({ type: "client.stop" }));
    window.setTimeout(() => {
      if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
        appState.ws.close();
      }
    }, 1200);
  }

  await stopMedia();
  setRunningState(false);
  setSessionStatus("Stopped.");

  if (!notifyServer && appState.ws) {
    appState.ws.close();
  }
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
        queuePlaybackChunk(payload.data_b64);
        break;
      case "server.text":
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
        appendCaption("Summary", "Session summary received.");
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
  };
}

async function startSession() {
  if (!appState.user) {
    throw new Error("Sign in before starting a session.");
  }

  elements.summary.innerHTML = "";
  appState.playbackCursor = 0;
  setRiskBadge("NORMAL");
  setSessionStatus("Creating session...");

  const idToken = await appState.user.getIdToken(true);
  const session = await createSession(idToken);
  appState.sessionId = session.id;

  setSessionStatus("Opening live websocket...");
  appState.ws = createLiveSocket(idToken, session.id);
  attachSocketHandlers(appState.ws);
  await waitForSocketOpen(appState.ws);

  await startAudioCapture();
  await startVideoCapture();

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
  try {
    await startSession();
  } catch (error) {
    appendCaption("Error", error.message || "Unable to start the session.");
    setSessionStatus("Start failed.");
    await stopSession({ notifyServer: false });
  }
});

elements.confirm.addEventListener("click", () => {
  if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
    return;
  }
  appState.ws.send(JSON.stringify({ type: "client.confirm" }));
});

elements.stop.addEventListener("click", async () => {
  await stopSession({ notifyServer: true });
});

elements.mode.addEventListener("change", updateGoalHint);
updateGoalHint();
void loadClientConfig();
