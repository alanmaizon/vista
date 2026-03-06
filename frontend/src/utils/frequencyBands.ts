export interface FrequencyBandSnapshot {
  low: number;
  mid: number;
  high: number;
  amplitude: number;
  beat: number;
  hasSignal: boolean;
}

interface FrequencyBandInput {
  frequencyData: Uint8Array;
  timeDomainData: Uint8Array;
  sampleRate: number;
  fftSize: number;
}

const BASS_RANGE: readonly [number, number] = [20, 250];
const MID_RANGE: readonly [number, number] = [250, 2000];
const HIGH_RANGE: readonly [number, number] = [2000, 8000];

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function hzToBin(frequencyHz: number, sampleRate: number, fftSize: number): number {
  const nyquist = sampleRate / 2;
  const normalized = clamp01(frequencyHz / nyquist);
  return Math.round(normalized * (fftSize / 2));
}

function averageRange(data: Uint8Array, startBin: number, endBin: number): number {
  const start = Math.max(0, Math.min(data.length - 1, startBin));
  const end = Math.max(start + 1, Math.min(data.length, endBin));
  let sum = 0;
  for (let index = start; index < end; index += 1) {
    sum += data[index];
  }
  return sum / Math.max(1, end - start);
}

function normalizeBand(
  range: readonly [number, number],
  frequencyData: Uint8Array,
  sampleRate: number,
  fftSize: number,
  gain: number,
  gamma: number,
): number {
  const startBin = hzToBin(range[0], sampleRate, fftSize);
  const endBin = hzToBin(range[1], sampleRate, fftSize);
  const average = averageRange(frequencyData, startBin, endBin) / 255;
  return Math.pow(clamp01(average * gain), gamma);
}

function normalizeAmplitude(timeDomainData: Uint8Array): number {
  let sum = 0;
  for (let index = 0; index < timeDomainData.length; index += 1) {
    const centered = timeDomainData[index] / 128 - 1;
    sum += centered * centered;
  }
  const rms = Math.sqrt(sum / Math.max(1, timeDomainData.length));
  return clamp01(rms * 2.8);
}

export function extractFrequencyBands({
  frequencyData,
  timeDomainData,
  sampleRate,
  fftSize,
}: FrequencyBandInput): FrequencyBandSnapshot {
  const low = normalizeBand(BASS_RANGE, frequencyData, sampleRate, fftSize, 2.2, 0.86);
  const mid = normalizeBand(MID_RANGE, frequencyData, sampleRate, fftSize, 2.5, 0.9);
  const high = normalizeBand(HIGH_RANGE, frequencyData, sampleRate, fftSize, 3.2, 1.05);
  const amplitude = Math.max(normalizeAmplitude(timeDomainData), (low * 0.55 + mid * 0.32 + high * 0.18));

  return {
    low,
    mid,
    high,
    amplitude: clamp01(amplitude),
    beat: 0,
    hasSignal: amplitude > 0.025 || low > 0.04 || mid > 0.04 || high > 0.03,
  };
}
