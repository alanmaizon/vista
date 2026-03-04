function downsampleBuffer(buffer, sourceRate, targetRate) {
  if (targetRate >= sourceRate) {
    return buffer;
  }
  const sampleRateRatio = sourceRate / targetRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }

  return result;
}

function floatToPcm16Bytes(floatBuffer) {
  const pcm = new Int16Array(floatBuffer.length);
  for (let i = 0; i < floatBuffer.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[i]));
    pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return new Uint8Array(pcm.buffer);
}

export function bytesToBase64(bytes) {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

export async function capturePcmClip({ durationMs = 2400 } = {}) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  });

  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const monitorGain = audioContext.createGain();
  monitorGain.gain.value = 0;
  const chunks = [];

  const cleanup = async () => {
    processor.disconnect();
    processor.onaudioprocess = null;
    source.disconnect();
    monitorGain.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    await audioContext.close();
  };

  return new Promise((resolve, reject) => {
    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      chunks.push(new Float32Array(input));
    };

    source.connect(processor);
    processor.connect(monitorGain);
    monitorGain.connect(audioContext.destination);

    window.setTimeout(async () => {
      try {
        const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
        const merged = new Float32Array(totalLength);
        let cursor = 0;
        for (const chunk of chunks) {
          merged.set(chunk, cursor);
          cursor += chunk.length;
        }
        const downsampled = downsampleBuffer(merged, audioContext.sampleRate, 16000);
        const pcmBytes = floatToPcm16Bytes(downsampled);
        await cleanup();
        resolve({
          bytes: pcmBytes,
          audioB64: bytesToBase64(pcmBytes),
          mime: "audio/pcm;rate=16000",
        });
      } catch (error) {
        await cleanup();
        reject(error);
      }
    }, durationMs);
  });
}
