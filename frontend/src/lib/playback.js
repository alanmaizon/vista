/**
 * Synthesize audio from a list of note events using the Web Audio API.
 *
 * @param {Object} options
 * @param {Array<{midi_note: number, beats?: number, duration_ms?: number}>} options.notes
 * @param {number} [options.tempo_bpm=120]
 * @param {string} [options.waveform="sine"]
 * @returns {Promise<void>} Resolves when playback finishes.
 */
export function playPhrase({ notes, tempo_bpm = 120, waveform = "sine" }) {
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

/**
 * Convert a MIDI note number to its frequency in Hz.
 * @param {number} n - MIDI note number (e.g. 69 = A4 = 440 Hz).
 * @returns {number}
 */
export function midiToFrequency(n) {
  return 440 * Math.pow(2, (n - 69) / 12);
}
