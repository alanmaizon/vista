import { appState } from "./state.js";
import { appendCaption } from "./ui.js";

export function toBase64(uint8Array) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < uint8Array.length; index += chunkSize) {
    const slice = uint8Array.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

export function fromBase64(base64Value) {
  const binary = atob(base64Value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export function downsampleBuffer(buffer, inputRate, outputRate) {
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

export function floatToPcm16Bytes(floatBuffer) {
  const output = new Int16Array(floatBuffer.length);
  for (let index = 0; index < floatBuffer.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[index]));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return new Uint8Array(output.buffer);
}

export async function ensureAudioContext() {
  if (!appState.audioContext) {
    appState.audioContext = new AudioContext({ latencyHint: "interactive" });
  }
  if (appState.audioContext.state === "suspended") {
    await appState.audioContext.resume();
  }
  return appState.audioContext;
}

export function queuePlaybackChunk(base64Data, mime = "audio/pcm;rate=24000") {
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

export function concatUint8Arrays(chunks) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

export async function captureOneShotPcmClip({ durationMs = 2400 } = {}) {
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
