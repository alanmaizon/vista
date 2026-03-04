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

/**
 * Compute RMS energy (in dB) for a Float32Array chunk.
 */
export function chunkEnergyDb(chunk) {
  let sum = 0;
  for (let i = 0; i < chunk.length; i += 1) {
    sum += chunk[i] * chunk[i];
  }
  const rms = Math.sqrt(sum / (chunk.length || 1));
  return rms > 0 ? 20 * Math.log10(rms) : -Infinity;
}

export async function capturePcmClip({
  durationMs = 2400,
  mode = "speech",
  trailingSilenceMs = 400,
  onsetThresholdDb = -45,
  maxMs = 10000,
} = {}) {
  const isMusic = mode === "music";

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: !isMusic,
      noiseSuppression: !isMusic,
      autoGainControl: !isMusic,
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

  const buildResult = (sampleRate) => {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const merged = new Float32Array(totalLength);
    let cursor = 0;
    for (const chunk of chunks) {
      merged.set(chunk, cursor);
      cursor += chunk.length;
    }
    const downsampled = downsampleBuffer(merged, sampleRate, 16000);
    const pcmBytes = floatToPcm16Bytes(downsampled);
    return {
      bytes: pcmBytes,
      audioB64: bytesToBase64(pcmBytes),
      mime: "audio/pcm;rate=16000",
    };
  };

  return new Promise((resolve, reject) => {
    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      chunks.push(new Float32Array(input));
    };

    source.connect(processor);
    processor.connect(monitorGain);
    monitorGain.connect(audioContext.destination);

    if (!isMusic) {
      // Speech mode: fixed-duration capture (unchanged behaviour)
      window.setTimeout(async () => {
        try {
          resolve(buildResult(audioContext.sampleRate));
          await cleanup();
        } catch (error) {
          await cleanup();
          reject(error);
        }
      }, durationMs);
      return;
    }

    // Music mode: adaptive energy-gated capture
    const preRollMs = 200;
    const checkIntervalMs = 10;
    const onsetFramesRequired = 3;
    let onsetDetected = false;
    let onsetTime = null;
    let consecutiveOnsetFrames = 0;
    let lastAboveTime = null;
    const startTime = Date.now();

    const interval = setInterval(async () => {
      try {
        const elapsed = Date.now() - startTime;

        // Check the latest chunk energy
        const latestChunk = chunks.length > 0 ? chunks[chunks.length - 1] : null;
        const energyDb = latestChunk ? chunkEnergyDb(latestChunk) : -Infinity;

        if (!onsetDetected) {
          if (energyDb >= onsetThresholdDb) {
            consecutiveOnsetFrames += 1;
            if (consecutiveOnsetFrames >= onsetFramesRequired) {
              onsetDetected = true;
              onsetTime = Date.now();
              lastAboveTime = Date.now();
            }
          } else {
            consecutiveOnsetFrames = 0;
          }

          // If no onset within maxMs, fall back to fixed duration
          if (elapsed >= durationMs && !onsetDetected) {
            clearInterval(interval);
            resolve(buildResult(audioContext.sampleRate));
            await cleanup();
            return;
          }
        } else {
          // Onset was detected — continue while energy is above threshold
          if (energyDb >= onsetThresholdDb) {
            lastAboveTime = Date.now();
          }

          const silenceDuration = Date.now() - lastAboveTime;
          const totalElapsed = Date.now() - startTime;

          if (silenceDuration >= trailingSilenceMs || totalElapsed >= maxMs) {
            clearInterval(interval);

            // Trim to include pre-roll before onset
            const preRollSamples = Math.round(
              (preRollMs / 1000) * audioContext.sampleRate,
            );
            const onsetElapsedMs = onsetTime - startTime;
            const onsetSampleIndex = Math.round(
              (onsetElapsedMs / 1000) * audioContext.sampleRate,
            );
            const keepFrom = Math.max(0, onsetSampleIndex - preRollSamples);

            // Rebuild chunks trimmed from keepFrom
            const totalLength = chunks.reduce(
              (sum, chunk) => sum + chunk.length,
              0,
            );
            const merged = new Float32Array(totalLength);
            let cursor = 0;
            for (const chunk of chunks) {
              merged.set(chunk, cursor);
              cursor += chunk.length;
            }
            const trimmed = merged.subarray(keepFrom);

            // Replace chunks with trimmed data
            chunks.length = 0;
            chunks.push(trimmed);

            resolve(buildResult(audioContext.sampleRate));
            await cleanup();
          }
        }
      } catch (error) {
        clearInterval(interval);
        await cleanup();
        reject(error);
      }
    }, checkIntervalMs);
  });
}
