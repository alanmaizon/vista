import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js";
import {
  getAuth,
  signInAnonymously,
  signInWithEmailAndPassword,
} from "https://www.gstatic.com/firebasejs/11.4.0/firebase-auth.js";
import { appState, elements } from "./state.js";
import { setAuthStatus, sessionRunning } from "./ui.js";
import { sanitizeInput, sanitizeJson, isValidEmail, validateFirebaseConfig } from "./sanitize.js";

export async function readApiPayload(response) {
  const raw = await response.text();
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    if (!response.ok) {
      throw new Error(raw.trim() || `Request failed with ${response.status}`);
    }
    throw new Error("Received an unreadable server response.");
  }
}

export function parseFirebaseConfig() {
  const raw = sanitizeInput(elements.firebaseConfig.value, { maxLength: 10000 });
  if (!raw) {
    throw new Error("Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.");
  }

  const config = sanitizeJson(raw);
  if (!config) {
    throw new Error("Firebase config must be valid JSON.");
  }

  const validation = validateFirebaseConfig(config);
  if (!validation.isValid) {
    throw new Error(`Invalid Firebase config: ${validation.errors.join(", ")}`);
  }

  return config;
}

export async function loadClientConfig() {
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

export async function loadMusicRuntimeStatus() {
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
    appState.crepeAvailable = Boolean(payload?.crepe_available);
    if (!appState.activeMusicScoreId && !sessionRunning()) {
      const renderStatus = appState.verovioAvailable
        ? "Verovio is available. Render notation will return SVG when a score is loaded."
        : "Verovio is not installed on the backend yet. Render notation will use MusicXML fallback until it is added.";
      const pitchStatus = appState.crepeAvailable
        ? " CREPE confirmation is active for focused clips."
        : " CREPE is not installed yet, so FastYIN remains the only pitch engine.";
      elements.scoreRender.textContent = `${renderStatus}${pitchStatus}`;
    }
    if (payload?.verovio_detail) {
      console.info(`[${appState.brand}][Verovio]`, payload.verovio_detail);
    }
    if (payload?.crepe_detail) {
      console.info(`[${appState.brand}][CREPE]`, payload.crepe_detail);
    }
  } catch {
    // Keep the default render placeholder when runtime status cannot be loaded.
  }
}

export async function ensureFirebase() {
  if (appState.auth) {
    return appState.auth;
  }
  const config = parseFirebaseConfig();
  appState.firebaseApp = getApps()[0] || initializeApp(config);
  appState.auth = getAuth(appState.firebaseApp);
  return appState.auth;
}

export async function signIn() {
  await loadClientConfig();
  const auth = await ensureFirebase();
  const email = sanitizeInput(elements.email.value, { maxLength: 254 });
  const password = elements.password.value;

  let credential;
  if (email && password) {
    if (!isValidEmail(email)) {
      throw new Error("Please enter a valid email address.");
    }
    credential = await signInWithEmailAndPassword(auth, email, password);
  } else {
    credential = await signInAnonymously(auth);
  }

  appState.user = credential.user;
  setAuthStatus(`Signed in as ${appState.user.email || appState.user.uid}`);
  await loadMusicRuntimeStatus();
}
