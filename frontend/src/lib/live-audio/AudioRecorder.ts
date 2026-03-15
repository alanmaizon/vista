import { getSharedAudioContext } from "./audioContext";
import { createWorkletFromSource } from "./audioworkletRegistry";
import audioProcessingWorklet from "./worklets/audioProcessing";
import volMeterWorklet from "./worklets/volMeter";

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";

  for (let index = 0; index < bytes.byteLength; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }

  return window.btoa(binary);
}

export class AudioRecorder {
  stream: MediaStream | undefined;
  audioContext: AudioContext | undefined;
  sourceNode: MediaStreamAudioSourceNode | undefined;
  recordingNode: AudioWorkletNode | undefined;
  volumeNode: AudioWorkletNode | undefined;
  onData: ((dataBase64: string) => void) | null = null;
  onVolume: ((volume: number) => void) | null = null;

  private startingPromise: Promise<void> | null = null;

  constructor(private readonly sampleRate = 16000) {}

  async start() {
    if (this.startingPromise) {
      await this.startingPromise;
      return;
    }
    if (this.stream) {
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("This browser does not support microphone capture.");
    }

    this.startingPromise = (async () => {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioContext = await getSharedAudioContext({ sampleRate: this.sampleRate });
      this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);

      const recordingWorkletUrl = createWorkletFromSource(
        "tutor-audio-processing",
        audioProcessingWorklet,
      );
      const volumeWorkletUrl = createWorkletFromSource("tutor-vol-meter", volMeterWorklet);

      try {
        await this.audioContext.audioWorklet.addModule(recordingWorkletUrl);
        await this.audioContext.audioWorklet.addModule(volumeWorkletUrl);
      } finally {
        URL.revokeObjectURL(recordingWorkletUrl);
        URL.revokeObjectURL(volumeWorkletUrl);
      }

      this.recordingNode = new AudioWorkletNode(this.audioContext, "tutor-audio-processing");
      this.recordingNode.port.onmessage = (event: MessageEvent) => {
        const arrayBuffer = event.data?.data?.int16arrayBuffer as ArrayBuffer | undefined;
        if (arrayBuffer && this.onData) {
          this.onData(arrayBufferToBase64(arrayBuffer));
        }
      };

      this.volumeNode = new AudioWorkletNode(this.audioContext, "tutor-vol-meter");
      this.volumeNode.port.onmessage = (event: MessageEvent) => {
        const volume = event.data?.volume;
        if (typeof volume === "number" && this.onVolume) {
          this.onVolume(volume);
        }
      };

      this.sourceNode.connect(this.recordingNode);
      this.sourceNode.connect(this.volumeNode);
    })();

    try {
      await this.startingPromise;
    } finally {
      this.startingPromise = null;
    }
  }

  stop() {
    const finalizeStop = () => {
      this.sourceNode?.disconnect();
      this.recordingNode?.disconnect();
      this.volumeNode?.disconnect();
      this.stream?.getTracks().forEach((track) => track.stop());
      void this.audioContext?.close().catch(() => {
        // Ignore close races while the browser settles the graph teardown.
      });
      this.stream = undefined;
      this.audioContext = undefined;
      this.sourceNode = undefined;
      this.recordingNode = undefined;
      this.volumeNode = undefined;
      if (this.onVolume) {
        this.onVolume(0);
      }
    };

    if (this.startingPromise) {
      void this.startingPromise.then(finalizeStop);
      return;
    }

    finalizeStop();
  }
}
