import { useEffect, useRef, useCallback, useState } from "react";
import { Mic, MicOff, Camera, CameraOff } from "lucide-react";

/**
 * MediaCapture – requests Mic and Camera permissions via the MediaDevices API,
 * captures audio blobs and sends them to the backend through the provided `send`
 * callback from useLiveConnection.
 *
 * @param {object}  props
 * @param {boolean} props.micEnabled    – whether mic capture is active
 * @param {boolean} props.cameraEnabled – whether camera capture is active
 * @param {function} props.send         – WebSocket send from useLiveConnection
 * @param {boolean} props.isConnected   – true when the WebSocket is open
 */
export default function MediaCapture({ micEnabled, cameraEnabled, send, isConnected }) {
  const micStreamRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const processorRef = useRef(null);
  const audioCtxRef = useRef(null);
  const [micActive, setMicActive] = useState(false);
  const [camActive, setCamActive] = useState(false);

  /* ---- helpers ---- */
  const floatTo16BitPCM = useCallback((float32) => {
    const buf = new ArrayBuffer(float32.length * 2);
    const view = new DataView(buf);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Uint8Array(buf);
  }, []);

  const toBase64 = useCallback((bytes) => {
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }, []);

  /* ---- Microphone ---- */
  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
      });
      micStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (!isConnected) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const pcm = floatTo16BitPCM(float32);
        send({
          type: "client.audio",
          mime: "audio/pcm;rate=16000",
          data_b64: toBase64(pcm),
        });
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setMicActive(true);
    } catch {
      setMicActive(false);
    }
  }, [isConnected, send, floatTo16BitPCM, toBase64]);

  const stopMic = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;
    setMicActive(false);
  }, []);

  /* ---- Camera ---- */
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: "environment" },
      });
      cameraStreamRef.current = stream;
      setCamActive(true);
    } catch {
      setCamActive(false);
    }
  }, []);

  const stopCamera = useCallback(() => {
    cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
    cameraStreamRef.current = null;
    setCamActive(false);
  }, []);

  /* ---- Lifecycle ---- */
  useEffect(() => {
    if (micEnabled && isConnected) {
      startMic();
    } else {
      stopMic();
    }
    return () => stopMic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micEnabled, isConnected]);

  useEffect(() => {
    if (cameraEnabled && isConnected) {
      startCamera();
    } else {
      stopCamera();
    }
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraEnabled, isConnected]);

  return (
    <div className="flex items-center gap-3">
      <span
        className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
          micActive
            ? "bg-green-500/20 text-green-300 border border-green-400/30"
            : "bg-white/10 text-white/50 border border-white/10"
        }`}
      >
        {micActive ? <Mic className="h-3 w-3" /> : <MicOff className="h-3 w-3" />}
        Mic
      </span>

      <span
        className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
          camActive
            ? "bg-green-500/20 text-green-300 border border-green-400/30"
            : "bg-white/10 text-white/50 border border-white/10"
        }`}
      >
        {camActive ? <Camera className="h-3 w-3" /> : <CameraOff className="h-3 w-3" />}
        Camera
      </span>
    </div>
  );
}
