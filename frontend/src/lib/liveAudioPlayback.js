function fromBase64(base64Value) {
  const binary = atob(base64Value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function pcm16ToFloat32(bytes) {
  const frameCount = Math.floor(bytes.byteLength / 2);
  const view = new DataView(bytes.buffer, bytes.byteOffset, frameCount * 2);
  const samples = new Float32Array(frameCount);

  for (let index = 0; index < frameCount; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 0x8000;
  }

  return samples;
}

export function createLiveAudioPlayback() {
  let audioContext = null;
  let playbackCursor = 0;

  async function ensureContext() {
    if (!audioContext) {
      const AudioContextCtor = window.AudioContext ?? window.webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error("Web Audio API is unavailable in this browser.");
      }
      audioContext = new AudioContextCtor({ latencyHint: "interactive" });
    }

    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    return audioContext;
  }

  async function enqueue(base64Data, mime = "audio/pcm;rate=24000") {
    if (typeof mime !== "string" || !mime.toLowerCase().startsWith("audio/pcm")) {
      return;
    }

    const context = await ensureContext();
    const bytes = fromBase64(base64Data);
    const samples = pcm16ToFloat32(bytes);
    if (!samples.length) {
      return;
    }

    const sampleRateMatch = /rate=(\d+)/i.exec(mime);
    const sampleRate = sampleRateMatch ? Number(sampleRateMatch[1]) : 24000;
    const audioBuffer = context.createBuffer(1, samples.length, sampleRate);
    audioBuffer.copyToChannel(samples, 0);

    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);

    const startAt = Math.max(context.currentTime, playbackCursor);
    source.start(startAt);
    playbackCursor = startAt + audioBuffer.duration;
  }

  async function close() {
    if (!audioContext) {
      return;
    }
    await audioContext.close();
    audioContext = null;
    playbackCursor = 0;
  }

  return {
    enqueue,
    ensureContext,
    close,
  };
}
