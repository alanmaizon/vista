/**
 * Synthesize audio from a list of note events using the Web Audio API.
 *
 * @param {Object} options
 * @param {Array<{midi_note: number, beats?: number, duration_ms?: number}>} options.notes
 * @param {number} [options.tempo_bpm=120]
 * @param {string} [options.waveform="sine"]
 * @param {HTMLAudioElement | null} [options.audioElement=null]
 * @returns {Promise<void>} Resolves when playback finishes.
 */
export async function playPhrase({ notes, tempo_bpm = 120, waveform = "sine", audioElement = null }) {
  if (!Array.isArray(notes) || !notes.length) {
    return;
  }

  const rendered = await renderPhraseToAudio({ notes, tempo_bpm, waveform });
  if (rendered) {
    await playRenderedPhrase({ blob: rendered, audioElement });
    return;
  }

  await playPhraseRealtime({ notes, tempo_bpm, waveform });
}

async function playPhraseRealtime({ notes, tempo_bpm = 120, waveform = "sine" }) {
  const ctx = new AudioContext();
  let currentTime = ctx.currentTime;
  const beatMs = 60000 / tempo_bpm;

  for (const note of notes) {
    const frequency = midiToFrequency(note.midi_note);
    const beats = note.beats ?? (note.duration_ms != null ? note.duration_ms / beatMs : 1);
    const durationSec = (beats * beatMs) / 1000;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = waveform;
    osc.frequency.setValueAtTime(frequency, currentTime);
    gain.gain.setValueAtTime(0.2, currentTime);
    osc.connect(gain).connect(ctx.destination);
    osc.start(currentTime);
    osc.stop(currentTime + durationSec);
    currentTime += durationSec;
  }

  const totalDuration = currentTime - ctx.currentTime;
  return new Promise((resolve) => {
    setTimeout(async () => {
      await ctx.close();
      resolve();
    }, totalDuration * 1000 + 50);
  });
}

async function renderPhraseToAudio({ notes, tempo_bpm = 120, waveform = "sine" }) {
  const OfflineAudioContextCtor = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  if (!OfflineAudioContextCtor) {
    return null;
  }

  const beatMs = 60000 / tempo_bpm;
  const sampleRate = 44100;
  const totalDurationSec =
    notes.reduce((sum, note) => {
      const beats = note.beats ?? (note.duration_ms != null ? note.duration_ms / beatMs : 1);
      return sum + (beats * beatMs) / 1000;
    }, 0) + 0.18;

  const frameCount = Math.max(1, Math.ceil(totalDurationSec * sampleRate));
  const ctx = new OfflineAudioContextCtor(1, frameCount, sampleRate);
  let currentTime = 0;

  for (const note of notes) {
    const frequency = midiToFrequency(note.midi_note);
    const beats = note.beats ?? (note.duration_ms != null ? note.duration_ms / beatMs : 1);
    const durationSec = Math.max(0.06, (beats * beatMs) / 1000);
    const attackSec = Math.min(0.018, durationSec * 0.18);
    const releaseSec = Math.min(0.06, durationSec * 0.24);
    const sustainEnd = Math.max(currentTime + attackSec, currentTime + durationSec - releaseSec);

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = waveform;
    osc.frequency.setValueAtTime(frequency, currentTime);

    gain.gain.setValueAtTime(0.0001, currentTime);
    gain.gain.linearRampToValueAtTime(0.2, currentTime + attackSec);
    gain.gain.setValueAtTime(0.18, sustainEnd);
    gain.gain.linearRampToValueAtTime(0.0001, currentTime + durationSec);

    osc.connect(gain).connect(ctx.destination);
    osc.start(currentTime);
    osc.stop(currentTime + durationSec);
    currentTime += durationSec;
  }

  const buffer = await ctx.startRendering();
  return audioBufferToWavBlob(buffer);
}

async function playRenderedPhrase({ blob, audioElement = null }) {
  const element = audioElement ?? new Audio();
  const objectUrl = URL.createObjectURL(blob);
  const cleanup = () => {
    element.pause();
    if (element.src === objectUrl) {
      element.removeAttribute("src");
      element.load();
    }
    URL.revokeObjectURL(objectUrl);
  };

  return new Promise((resolve, reject) => {
    const onEnded = () => {
      detach();
      cleanup();
      resolve();
    };
    const onError = () => {
      detach();
      cleanup();
      reject(new Error("Audio playback failed."));
    };
    const detach = () => {
      element.removeEventListener("ended", onEnded);
      element.removeEventListener("error", onError);
    };

    element.preload = "auto";
    element.currentTime = 0;
    element.src = objectUrl;
    element.addEventListener("ended", onEnded, { once: true });
    element.addEventListener("error", onError, { once: true });

    const playAttempt = element.play();
    if (playAttempt?.catch) {
      playAttempt.catch((error) => {
        detach();
        cleanup();
        reject(error);
      });
    }
  });
}

function audioBufferToWavBlob(buffer) {
  const channelData = buffer.getChannelData(0);
  const dataView = new DataView(new ArrayBuffer(44 + channelData.length * 2));

  writeAscii(dataView, 0, "RIFF");
  dataView.setUint32(4, 36 + channelData.length * 2, true);
  writeAscii(dataView, 8, "WAVE");
  writeAscii(dataView, 12, "fmt ");
  dataView.setUint32(16, 16, true);
  dataView.setUint16(20, 1, true);
  dataView.setUint16(22, 1, true);
  dataView.setUint32(24, buffer.sampleRate, true);
  dataView.setUint32(28, buffer.sampleRate * 2, true);
  dataView.setUint16(32, 2, true);
  dataView.setUint16(34, 16, true);
  writeAscii(dataView, 36, "data");
  dataView.setUint32(40, channelData.length * 2, true);

  let offset = 44;
  for (let i = 0; i < channelData.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, channelData[i]));
    dataView.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }

  return new Blob([dataView.buffer], { type: "audio/wav" });
}

function writeAscii(dataView, offset, value) {
  for (let i = 0; i < value.length; i += 1) {
    dataView.setUint8(offset + i, value.charCodeAt(i));
  }
}

/**
 * Convert a MIDI note number to its frequency in Hz.
 * @param {number} n - MIDI note number (e.g. 69 = A4 = 440 Hz).
 * @returns {number}
 */
export function midiToFrequency(n) {
  return 440 * Math.pow(2, (n - 69) / 12);
}
