import { extractFrequencyBands, type FrequencyBandSnapshot } from "../utils/frequencyBands";

export type AudioSourceMode = "microphone" | "element";

export interface AudioAnalyzerConnectOptions {
  audioElement?: HTMLAudioElement | null;
}

const IDLE_CENTER = 0.1;
const ELEMENT_SOURCE_CACHE = new WeakMap<HTMLMediaElement, MediaElementAudioSourceNode>();

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function lerp(current: number, target: number, amount: number): number {
  return current + (target - current) * amount;
}

function createIdleSnapshot(timeSeconds: number): FrequencyBandSnapshot {
  // Keep the orb breathing even when there is no active input device.
  const low = IDLE_CENTER + Math.sin(timeSeconds * 0.7) * 0.035;
  const mid = IDLE_CENTER * 0.75 + Math.sin(timeSeconds * 1.1 + 1.2) * 0.028;
  const high = IDLE_CENTER * 0.55 + Math.sin(timeSeconds * 1.7 + 2.8) * 0.018;
  const amplitude = IDLE_CENTER * 0.82 + Math.sin(timeSeconds * 0.43 + 0.7) * 0.025;
  return {
    low: clamp01(low),
    mid: clamp01(mid),
    high: clamp01(high),
    amplitude: clamp01(amplitude),
    beat: 0,
    hasSignal: false,
  };
}

export class AudioAnalyzer {
  private readonly fftSize = 1024;

  private context: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | MediaElementAudioSourceNode | null = null;
  private mediaStream: MediaStream | null = null;
  private connectedElement: HTMLAudioElement | null = null;
  private frequencyData: Uint8Array | null = null;
  private timeDomainData: Uint8Array | null = null;
  private smoothed: FrequencyBandSnapshot = createIdleSnapshot(0);
  private beatPulse = 0;
  private lastLow = 0;
  private sourceMode: AudioSourceMode | null = null;

  private getAudioContextCtor(): typeof AudioContext {
    const extendedWindow = window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext };
    const audioContextCtor = extendedWindow.AudioContext ?? extendedWindow.webkitAudioContext;
    if (!audioContextCtor) {
      throw new Error("Web Audio API is not available in this browser.");
    }
    return audioContextCtor;
  }

  private async ensureContext(): Promise<AudioContext> {
    if (!this.context) {
      const AudioContextCtor = this.getAudioContextCtor();
      this.context = new AudioContextCtor();
    }
    if (this.context.state === "suspended") {
      await this.context.resume();
    }
    return this.context;
  }

  private ensureAnalyser(context: AudioContext): AnalyserNode {
    if (!this.analyser) {
      this.analyser = context.createAnalyser();
      this.analyser.fftSize = this.fftSize;
      this.analyser.smoothingTimeConstant = 0.78;
      this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
      this.timeDomainData = new Uint8Array(this.analyser.fftSize);
    }
    return this.analyser;
  }

  async connect(sourceMode: AudioSourceMode, options: AudioAnalyzerConnectOptions = {}): Promise<void> {
    if (sourceMode === "microphone") {
      await this.connectMicrophone();
      return;
    }
    await this.connectElement(options.audioElement ?? null);
  }

  async connectMicrophone(): Promise<void> {
    if (this.sourceMode === "microphone" && this.analyser && this.mediaStream) {
      return;
    }
    this.disconnect(false);
    const context = await this.ensureContext();
    const analyser = this.ensureAnalyser(context);
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      video: false,
    });
    this.sourceNode = context.createMediaStreamSource(this.mediaStream);
    this.sourceNode.connect(analyser);
    this.sourceMode = "microphone";
  }

  async connectElement(audioElement: HTMLAudioElement | null): Promise<void> {
    if (!audioElement) {
      this.disconnect(false);
      return;
    }
    if (this.sourceMode === "element" && this.connectedElement === audioElement && this.sourceNode && this.analyser) {
      return;
    }
    this.disconnect(false);
    const context = await this.ensureContext();
    const analyser = this.ensureAnalyser(context);
    const cachedSource = ELEMENT_SOURCE_CACHE.get(audioElement);
    this.sourceNode = cachedSource ?? context.createMediaElementSource(audioElement);
    if (!cachedSource) {
      ELEMENT_SOURCE_CACHE.set(audioElement, this.sourceNode);
    }
    this.sourceNode.connect(analyser);
    analyser.connect(context.destination);
    this.sourceMode = "element";
    this.connectedElement = audioElement;
  }

  sample(timeSeconds: number): FrequencyBandSnapshot {
    if (!this.analyser || !this.context || !this.frequencyData || !this.timeDomainData) {
      this.smoothed = createIdleSnapshot(timeSeconds);
      return this.smoothed;
    }

    this.analyser.getByteFrequencyData(this.frequencyData);
    this.analyser.getByteTimeDomainData(this.timeDomainData);

    const snapshot = extractFrequencyBands({
      frequencyData: this.frequencyData,
      timeDomainData: this.timeDomainData,
      sampleRate: this.context.sampleRate,
      fftSize: this.analyser.fftSize,
    });

    // A light beat detector helps the orb punctuate percussive accents.
    if (snapshot.low > 0.58 && snapshot.low - this.lastLow > 0.05) {
      this.beatPulse = 1;
    }
    this.beatPulse = Math.max(0, this.beatPulse * 0.92 - 0.012);
    this.lastLow = snapshot.low;

    this.smoothed = {
      low: lerp(this.smoothed.low, snapshot.low, snapshot.hasSignal ? 0.18 : 0.04),
      mid: lerp(this.smoothed.mid, snapshot.mid, snapshot.hasSignal ? 0.15 : 0.04),
      high: lerp(this.smoothed.high, snapshot.high, snapshot.hasSignal ? 0.22 : 0.05),
      amplitude: lerp(this.smoothed.amplitude, snapshot.amplitude, snapshot.hasSignal ? 0.16 : 0.05),
      beat: Math.max(this.beatPulse, snapshot.low * 0.28),
      hasSignal: snapshot.hasSignal,
    };

    return this.smoothed;
  }

  disconnect(closeContext = false): void {
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    this.connectedElement = null;
    this.sourceMode = null;

    if (closeContext && this.context) {
      void this.context.close();
      this.context = null;
      this.analyser = null;
      this.frequencyData = null;
      this.timeDomainData = null;
    }
  }

  dispose(): void {
    this.disconnect(true);
  }
}
