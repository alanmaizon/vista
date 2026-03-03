import { appState, elements } from "./state.js";
import { sessionRunning, hasVisualSourceEnabled, updateCaptureGuidance, refreshMediaButtons, appendCaption } from "./ui.js";
import { ensureAudioContext, downsampleBuffer, floatToPcm16Bytes, toBase64 } from "./audio.js";
import { usesDeterministicLivePhraseCapture } from "./music-score.js";

export async function enableMicCapture() {
  if (!appState.micEnabled || !sessionRunning() || appState.micStream || usesDeterministicLivePhraseCapture()) {
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

export async function disableMicCapture() {
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

export function updatePreviewSource() {
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

export async function ensureCameraCapture() {
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

export async function ensureScreenCapture() {
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

export async function stopCameraCapture() {
  if (appState.camStream) {
    for (const track of appState.camStream.getTracks()) {
      track.stop();
    }
    appState.camStream = null;
  }
  updatePreviewSource();
}

export async function stopScreenCapture() {
  if (appState.screenStream) {
    for (const track of appState.screenStream.getTracks()) {
      track.stop();
    }
    appState.screenStream = null;
  }
  updatePreviewSource();
  restartVisualFrameTimer();
}

export function capturePreviewFrame() {
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

export function sendVisualFrame(base64Data) {
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

export function restartVisualFrameTimer() {
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

export async function syncVisualCapture() {
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

export async function captureScreenshot() {
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

export async function stopMedia() {
  if (appState.videoTimer) {
    clearInterval(appState.videoTimer);
    appState.videoTimer = null;
  }

  await disableMicCapture();
  await stopScreenCapture();
  await stopCameraCapture();
}
