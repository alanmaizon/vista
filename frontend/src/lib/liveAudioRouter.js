import {
  bytesToBase64,
  chunkEnergyDb,
  downsampleBuffer,
  floatToPcm16Bytes,
} from "./audioCapture";

const TARGET_SAMPLE_RATE = 16000;
const ANALYSIS_FRAME_SIZE = 2048;
const MUSIC_SILENCE_MS = 340;
const CONFIDENCE_SMOOTHING = 0.28;
const MODE_SWITCH_CONFIRM_FRAMES = 2;
const MUSIC_PITCH_GATE = 0.5;
const SPEECH_ACTIVITY_ENTER = 0.7;
const SPEECH_ACTIVITY_HOLD = 0.4;
const SPEECH_ACTIVITY_ENTER_DB = -42;
const SPEECH_ACTIVITY_HOLD_DB = -52;
const SPEECH_ACTIVITY_ENTER_ZCR = 0.045;
const SPEECH_CONFIRM_FRAMES = 2;
const SPEECH_PAUSE_FLUSH_MS = 550;
const STABLE_NOTE_MIN_FRAMES = 4;
const STABLE_NOTE_MAX_CENTS_SPAN = 35;

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function smoothValue(previous, next, alpha = CONFIDENCE_SMOOTHING) {
  return previous + (next - previous) * alpha;
}

function centsBetween(aHz, bHz) {
  if (!aHz || !bHz) {
    return Infinity;
  }
  return Math.abs(1200 * Math.log2(aHz / bHz));
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

function computeZeroCrossingRate(buffer) {
  let crossings = 0;
  for (let index = 1; index < buffer.length; index += 1) {
    const previous = buffer[index - 1];
    const current = buffer[index];
    if ((previous >= 0 && current < 0) || (previous < 0 && current >= 0)) {
      crossings += 1;
    }
  }
  return crossings / Math.max(1, buffer.length - 1);
}

function computeSpectralCentroid(frequencyData, sampleRate) {
  let weightedSum = 0;
  let magnitudeSum = 0;
  const binHz = sampleRate / 2 / Math.max(1, frequencyData.length);
  for (let index = 0; index < frequencyData.length; index += 1) {
    const magnitude = frequencyData[index] / 255;
    weightedSum += magnitude * index * binHz;
    magnitudeSum += magnitude;
  }
  if (!magnitudeSum) {
    return 0;
  }
  return weightedSum / magnitudeSum;
}

function detectPitch(buffer, sampleRate) {
  let rms = 0;
  for (let index = 0; index < buffer.length; index += 1) {
    rms += buffer[index] * buffer[index];
  }
  rms = Math.sqrt(rms / Math.max(1, buffer.length));
  if (rms < 0.01) {
    return { hz: null, clarity: 0 };
  }

  let bestOffset = -1;
  let bestCorrelation = 0;
  const minOffset = Math.floor(sampleRate / 1200);
  const maxOffset = Math.floor(sampleRate / 65);

  for (let offset = minOffset; offset <= maxOffset; offset += 1) {
    let correlation = 0;
    for (let index = 0; index < buffer.length - offset; index += 1) {
      correlation += buffer[index] * buffer[index + offset];
    }
    correlation /= buffer.length - offset;
    if (correlation > bestCorrelation) {
      bestCorrelation = correlation;
      bestOffset = offset;
    }
  }

  if (bestOffset < 0 || bestCorrelation < 0.015) {
    return { hz: null, clarity: 0 };
  }

  return {
    hz: sampleRate / bestOffset,
    clarity: clamp01(bestCorrelation * 18),
  };
}

function hzToMidi(hz) {
  return Math.round(69 + 12 * Math.log2(hz / 440));
}

function midiToNoteName(midi) {
  const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const name = names[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - 1;
  return `${name}${octave}`;
}

function estimateRhythmPattern(onsetTimes) {
  if (onsetTimes.length < 2) {
    return null;
  }
  const intervals = [];
  for (let index = 1; index < onsetTimes.length; index += 1) {
    intervals.push(onsetTimes[index] - onsetTimes[index - 1]);
  }
  const averageInterval =
    intervals.reduce((sum, interval) => sum + interval, 0) / Math.max(1, intervals.length);
  const tempo = averageInterval > 0 ? Math.round(60000 / averageInterval) : null;
  const pattern = intervals.slice(0, 8).map((interval) => Math.max(1, Math.round(interval / 120)));
  return { tempo, pattern };
}

export function classifyAudioFrame({
  energyDb,
  zeroCrossingRate,
  spectralCentroid,
  pitch,
}) {
  if (energyDb < -58) {
    return {
      mode: "SILENCE",
      speechConfidence: 0,
      musicConfidence: 0,
    };
  }

  const energyConfidence = clamp01((energyDb + 58) / 26);
  const speechConfidence = clamp01(
    energyConfidence * 0.4 +
      clamp01(spectralCentroid / 2600) * 0.35 +
      clamp01(zeroCrossingRate * 18) * 0.25,
  );
  const musicConfidence = clamp01(
    energyConfidence * 0.3 +
      (pitch.hz ? pitch.clarity * 0.55 : 0) +
      clamp01(1 - Math.abs(spectralCentroid - 1100) / 1400) * 0.15,
  );

  if (musicConfidence >= 0.6 && musicConfidence > speechConfidence + 0.08) {
    return { mode: "MUSIC", speechConfidence, musicConfidence };
  }
  if (speechConfidence >= 0.52) {
    return { mode: "SPEECH", speechConfidence, musicConfidence };
  }
  return { mode: "SILENCE", speechConfidence, musicConfidence };
}

export function resolveAudioMode({
  currentMode,
  energyDb,
  speechConfidence,
  musicConfidence,
  pitchConfidence,
}) {
  if (energyDb < -58) {
    return "SILENCE";
  }

  const musicDominant =
    musicConfidence >= 0.66 &&
    musicConfidence > speechConfidence + 0.12 &&
    pitchConfidence >= MUSIC_PITCH_GATE;
  const speechDominant =
    speechConfidence >= 0.58 &&
    (speechConfidence > musicConfidence - 0.04 || pitchConfidence < 0.42);

  if (currentMode === "MUSIC") {
    if (energyDb < -54) {
      return "SILENCE";
    }
    if (musicConfidence >= 0.46 || pitchConfidence >= 0.62) {
      return "MUSIC";
    }
    if (speechConfidence >= 0.72 && speechConfidence > musicConfidence + 0.16) {
      return "SPEECH";
    }
    return "MUSIC";
  }

  if (currentMode === "SPEECH") {
    if (energyDb < -54) {
      return "SILENCE";
    }
    if (speechConfidence >= 0.42 && speechConfidence >= musicConfidence - 0.08) {
      return "SPEECH";
    }
    if (musicDominant) {
      return "MUSIC";
    }
    return "SPEECH";
  }

  if (musicDominant) {
    return "MUSIC";
  }
  if (speechDominant) {
    return "SPEECH";
  }
  return "SILENCE";
}

export function resolveSpeechActivity({
  active,
  energyDb,
  speechConfidence,
  zeroCrossingRate,
  pitchConfidence,
}) {
  if (energyDb < -55) {
    return false;
  }

  if (!active) {
    return (
      energyDb >= SPEECH_ACTIVITY_ENTER_DB &&
      speechConfidence >= SPEECH_ACTIVITY_ENTER &&
      zeroCrossingRate >= SPEECH_ACTIVITY_ENTER_ZCR &&
      !(pitchConfidence > 0.84 && zeroCrossingRate < 0.03)
    );
  }

  return speechConfidence >= SPEECH_ACTIVITY_HOLD && energyDb >= SPEECH_ACTIVITY_HOLD_DB;
}

export function shouldEmitStableNote(noteHold) {
  if (!noteHold) {
    return false;
  }
  return (
    noteHold.frames >= STABLE_NOTE_MIN_FRAMES &&
    noteHold.confidence >= 0.68 &&
    centsBetween(noteHold.minHz, noteHold.maxHz) <= STABLE_NOTE_MAX_CENTS_SPAN
  );
}

export function createLiveAudioRouter({
  eventBus = null,
  onSpeechChunk = null,
  onSpeechPause = null,
  onLevels = null,
  onModeChange = null,
} = {}) {
  let audioContext = null;
  let mediaStream = null;
  let sourceNode = null;
  let processorNode = null;
  let workletNode = null;
  let analyserNode = null;
  let monitorGain = null;
  let analyserData = null;
  let workletFrameQueue = [];
  let workletSamplesQueued = 0;
  let started = false;
  let currentMode = "SILENCE";
  let pendingMode = "SILENCE";
  let pendingModeFrames = 0;
  let lastMetricsEmitAt = 0;
  let smoothedSpeechConfidence = 0;
  let smoothedMusicConfidence = 0;
  let speechActive = false;
  let speechCandidateFrames = 0;
  let speechSegmentOpen = false;
  let speechPauseTimer = null;
  let speechLeadInChunks = [];
  let noteHold = null;
  let phraseState = {
    chunks: [],
    noteNames: [],
    onsetTimes: [],
    startedAt: 0,
    lastMusicAt: 0,
    lastNoteEmitAt: 0,
    lastOnsetAt: 0,
  };

  function emit(type, payload) {
    if (!eventBus) {
      return;
    }
    eventBus.emit(type, payload);
  }

  function clearSpeechPauseTimer() {
    if (speechPauseTimer === null) {
      return;
    }
    window.clearTimeout(speechPauseTimer);
    speechPauseTimer = null;
  }

  function scheduleSpeechPauseFlush() {
    if (!speechSegmentOpen || speechPauseTimer !== null) {
      return;
    }
    speechPauseTimer = window.setTimeout(() => {
      speechPauseTimer = null;
      if (speechActive || !speechSegmentOpen) {
        return;
      }
      speechSegmentOpen = false;
      speechCandidateFrames = 0;
      speechLeadInChunks = [];
      onSpeechPause?.();
    }, SPEECH_PAUSE_FLUSH_MS);
  }

  function resetPhrase() {
    noteHold = null;
    phraseState = {
      chunks: [],
      noteNames: [],
      onsetTimes: [],
      startedAt: 0,
      lastMusicAt: 0,
      lastNoteEmitAt: 0,
      lastOnsetAt: 0,
    };
  }

  function emitNoteEvent(noteName, pitchHz, velocity, confidence) {
    const payload = {
      type: "NOTE_PLAYED",
      pitch: noteName,
      frequency: pitchHz,
      velocity,
      confidence,
      occurredAt: Date.now(),
    };
    emit("music.note", payload);
  }

  function finalizePhrase() {
    if (!phraseState.startedAt || !phraseState.chunks.length) {
      resetPhrase();
      return;
    }

    const durationMs = Math.max(0, phraseState.lastMusicAt - phraseState.startedAt);
    const audioBytes = concatUint8Arrays(phraseState.chunks);
    if (phraseState.noteNames.length >= 2) {
      emit("music.phrase", {
        type: "PHRASE_PLAYED",
        notes: phraseState.noteNames,
        durationMs,
        audioB64: bytesToBase64(audioBytes),
        mime: "audio/pcm;rate=16000",
        occurredAt: Date.now(),
      });
      resetPhrase();
      return;
    }

    const rhythm = estimateRhythmPattern(phraseState.onsetTimes);
    if (rhythm && rhythm.tempo) {
      emit("music.rhythm", {
        type: "RHYTHM_PATTERN",
        tempo: rhythm.tempo,
        pattern: rhythm.pattern,
        durationMs,
        occurredAt: Date.now(),
      });
    }
    resetPhrase();
  }

  function trackMusicFrame({
    pcmBytes,
    pitch,
    energyDb,
    velocity,
  }) {
    const now = Date.now();
    if (!phraseState.startedAt) {
      phraseState.startedAt = now;
    }
    phraseState.lastMusicAt = now;
    phraseState.chunks.push(pcmBytes);
    if (phraseState.chunks.length > 72) {
      phraseState.chunks.shift();
    }

    if (energyDb > -34 && now - phraseState.lastOnsetAt > 140) {
      phraseState.onsetTimes.push(now);
      phraseState.lastOnsetAt = now;
      if (phraseState.onsetTimes.length > 16) {
        phraseState.onsetTimes.shift();
      }
    }

    if (!pitch.hz || pitch.clarity < 0.56) {
      return;
    }

    const midi = hzToMidi(pitch.hz);
    const noteName = midiToNoteName(midi);
    if (!noteHold || noteHold.noteName !== noteName) {
      noteHold = {
        noteName,
        pitchHz: pitch.hz,
        frames: 1,
        maxVelocity: velocity,
        confidence: pitch.clarity,
        minHz: pitch.hz,
        maxHz: pitch.hz,
        emitted: false,
      };
      return;
    }

    noteHold.frames += 1;
    noteHold.pitchHz = pitch.hz;
    noteHold.maxVelocity = Math.max(noteHold.maxVelocity, velocity);
    noteHold.confidence = Math.max(noteHold.confidence, pitch.clarity);
    noteHold.minHz = Math.min(noteHold.minHz, pitch.hz);
    noteHold.maxHz = Math.max(noteHold.maxHz, pitch.hz);

    if (!noteHold.emitted && shouldEmitStableNote(noteHold) && now - phraseState.lastNoteEmitAt > 220) {
      phraseState.lastNoteEmitAt = now;
      noteHold.emitted = true;
      if (phraseState.noteNames.at(-1) !== noteHold.noteName) {
        phraseState.noteNames.push(noteHold.noteName);
      }
      emitNoteEvent(noteHold.noteName, noteHold.pitchHz, noteHold.maxVelocity, noteHold.confidence);
    }
  }

  function processInputFrame(input, sampleRate) {
    const downsampled = downsampleBuffer(input, sampleRate, TARGET_SAMPLE_RATE);
    const pcmBytes = floatToPcm16Bytes(downsampled);
    const energyDb = chunkEnergyDb(input);
    const zeroCrossingRate = computeZeroCrossingRate(input);
    analyserNode.getByteFrequencyData(analyserData);
    const spectralCentroid = computeSpectralCentroid(analyserData, sampleRate);
    const pitch = detectPitch(input, sampleRate);
    const velocity = clamp01((energyDb + 55) / 24);
    const classification = classifyAudioFrame({
      energyDb,
      zeroCrossingRate,
      spectralCentroid,
      pitch,
    });
    smoothedSpeechConfidence = smoothValue(
      smoothedSpeechConfidence,
      classification.speechConfidence,
    );
    smoothedMusicConfidence = smoothValue(
      smoothedMusicConfidence,
      classification.musicConfidence,
    );
    const resolvedMode = resolveAudioMode({
      currentMode,
      energyDb,
      speechConfidence: smoothedSpeechConfidence,
      musicConfidence: smoothedMusicConfidence,
      pitchConfidence: pitch.clarity,
    });
    const wasSpeechActive = speechActive;
    speechActive = resolveSpeechActivity({
      active: speechActive,
      energyDb,
      speechConfidence: smoothedSpeechConfidence,
      zeroCrossingRate,
      pitchConfidence: pitch.clarity,
    });

    if (resolvedMode === pendingMode) {
      pendingModeFrames += 1;
    } else {
      pendingMode = resolvedMode;
      pendingModeFrames = 1;
    }

    if (pendingModeFrames >= MODE_SWITCH_CONFIRM_FRAMES && pendingMode !== currentMode) {
      currentMode = pendingMode;
      onModeChange?.(currentMode);
      emit("audio.mode", { mode: currentMode, occurredAt: Date.now() });
    }

    if (Date.now() - lastMetricsEmitAt > 90) {
      lastMetricsEmitAt = Date.now();
      onLevels?.({
        mode: currentMode,
        energyDb,
        speechConfidence: smoothedSpeechConfidence,
        musicConfidence: smoothedMusicConfidence,
        speechActive,
        pitchHz: pitch.hz,
        pitchConfidence: pitch.clarity,
      });
    }

    if (speechActive) {
      clearSpeechPauseTimer();
      if (!speechSegmentOpen) {
        speechCandidateFrames += 1;
        speechLeadInChunks.push(pcmBytes);
        if (speechLeadInChunks.length > SPEECH_CONFIRM_FRAMES + 1) {
          speechLeadInChunks.shift();
        }
        if (speechCandidateFrames < SPEECH_CONFIRM_FRAMES) {
          return;
        }
        speechSegmentOpen = true;
        const bufferedChunks = speechLeadInChunks;
        speechLeadInChunks = [];
        bufferedChunks.forEach((chunk) => onSpeechChunk?.(chunk));
      } else {
        onSpeechChunk?.(pcmBytes);
      }
    } else if (currentMode === "MUSIC") {
      speechCandidateFrames = 0;
      speechLeadInChunks = [];
      trackMusicFrame({
        pcmBytes,
        pitch,
        energyDb,
        velocity,
      });
    } else if (phraseState.startedAt && Date.now() - phraseState.lastMusicAt > MUSIC_SILENCE_MS) {
      speechCandidateFrames = 0;
      speechLeadInChunks = [];
      finalizePhrase();
    } else {
      speechCandidateFrames = 0;
      speechLeadInChunks = [];
    }

    if (wasSpeechActive && !speechActive) {
      scheduleSpeechPauseFlush();
    } else if (!speechActive && speechSegmentOpen) {
      scheduleSpeechPauseFlush();
    }
  }

  function pullQueuedWorkletFrame() {
    if (workletSamplesQueued < ANALYSIS_FRAME_SIZE) {
      return null;
    }

    const frame = new Float32Array(ANALYSIS_FRAME_SIZE);
    let offset = 0;
    while (offset < ANALYSIS_FRAME_SIZE && workletFrameQueue.length) {
      const head = workletFrameQueue[0];
      const remaining = ANALYSIS_FRAME_SIZE - offset;
      if (head.length <= remaining) {
        frame.set(head, offset);
        offset += head.length;
        workletSamplesQueued -= head.length;
        workletFrameQueue.shift();
      } else {
        frame.set(head.subarray(0, remaining), offset);
        workletFrameQueue[0] = head.subarray(remaining);
        workletSamplesQueued -= remaining;
        offset += remaining;
      }
    }
    return frame;
  }

  function queueWorkletChunk(chunk, sampleRate) {
    if (!(chunk instanceof Float32Array) || !chunk.length) {
      return;
    }
    workletFrameQueue.push(chunk);
    workletSamplesQueued += chunk.length;

    let frame = pullQueuedWorkletFrame();
    while (frame) {
      processInputFrame(frame, sampleRate);
      frame = pullQueuedWorkletFrame();
    }
  }

  async function start() {
    if (started) {
      return;
    }

    const AudioContextCtor = window.AudioContext ?? window.webkitAudioContext;
    if (!AudioContextCtor) {
      throw new Error("Web Audio API is unavailable in this browser.");
    }

    audioContext = new AudioContextCtor({ latencyHint: "interactive" });
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    const audioConstraints = {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };
    const supportedConstraints = navigator.mediaDevices.getSupportedConstraints?.();
    if (supportedConstraints?.voiceIsolation) {
      audioConstraints.voiceIsolation = true;
    }

    mediaStream = await navigator.mediaDevices.getUserMedia({
      // Guided live tutor speech is speech-optimized. Raw music capture still
      // goes through capturePcmClip({ mode: "music" }) with processing disabled.
      audio: audioConstraints,
      video: false,
    });

    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = ANALYSIS_FRAME_SIZE;
    analyserData = new Uint8Array(analyserNode.frequencyBinCount);
    monitorGain = audioContext.createGain();
    monitorGain.gain.value = 0;
    sourceNode.connect(analyserNode);
    analyserNode.connect(monitorGain);

    if (audioContext.audioWorklet && typeof window.AudioWorkletNode === "function") {
      await audioContext.audioWorklet.addModule(
        new URL("../audio/liveAudioRouterProcessor.js", import.meta.url),
      );
      workletNode = new window.AudioWorkletNode(audioContext, "live-audio-router-processor");
      workletNode.port.onmessage = (event) => {
        queueWorkletChunk(event.data, audioContext.sampleRate);
      };
      sourceNode.connect(workletNode);
      workletNode.connect(monitorGain);
    } else {
      processorNode = audioContext.createScriptProcessor(ANALYSIS_FRAME_SIZE, 1, 1);
      processorNode.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        processInputFrame(input, audioContext.sampleRate);
      };
      analyserNode.connect(processorNode);
      processorNode.connect(monitorGain);
    }

    monitorGain.connect(audioContext.destination);
    started = true;
  }

  async function stop() {
    if (!started) {
      return;
    }

    clearSpeechPauseTimer();
    if (speechSegmentOpen) {
      speechSegmentOpen = false;
      onSpeechPause?.();
    }

    if (processorNode) {
      processorNode.disconnect();
      processorNode.onaudioprocess = null;
    }
    if (workletNode) {
      workletNode.port.onmessage = null;
      workletNode.disconnect();
    }
    analyserNode.disconnect();
    sourceNode.disconnect();
    monitorGain.disconnect();
    mediaStream.getTracks().forEach((track) => track.stop());
    await audioContext.close();

    audioContext = null;
    mediaStream = null;
    sourceNode = null;
    processorNode = null;
    workletNode = null;
    analyserNode = null;
    monitorGain = null;
    analyserData = null;
    workletFrameQueue = [];
    workletSamplesQueued = 0;
    started = false;
    currentMode = "SILENCE";
    pendingMode = "SILENCE";
    pendingModeFrames = 0;
    lastMetricsEmitAt = 0;
    smoothedSpeechConfidence = 0;
    smoothedMusicConfidence = 0;
    speechActive = false;
    speechCandidateFrames = 0;
    speechSegmentOpen = false;
    speechLeadInChunks = [];
    resetPhrase();
  }

  return {
    start,
    stop,
  };
}
