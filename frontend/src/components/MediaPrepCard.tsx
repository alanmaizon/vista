import { useEffect, useRef } from "react";
import type { ChangeEvent } from "react";

interface MediaPrepCardProps {
  busyKind: "microphone" | "camera" | null;
  cameraReady: boolean;
  cameraStream: MediaStream | null;
  error: string | null;
  microphoneReady: boolean;
  onRequestCamera: () => Promise<void>;
  onRequestMicrophone: () => Promise<void>;
  onWorksheetChange: (file: File | null) => void;
  supportsMediaDevices: boolean;
  worksheetAttached: boolean;
  worksheetName: string | null;
  worksheetPreviewUrl: string | null;
}

export function MediaPrepCard({
  busyKind,
  cameraReady,
  cameraStream,
  error,
  microphoneReady,
  onRequestCamera,
  onRequestMicrophone,
  onWorksheetChange,
  supportsMediaDevices,
  worksheetAttached,
  worksheetName,
  worksheetPreviewUrl,
}: MediaPrepCardProps) {
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const node = cameraVideoRef.current;
    if (!node) {
      return;
    }
    node.srcObject = cameraStream;
  }, [cameraStream]);

  function handleWorksheetSelection(event: ChangeEvent<HTMLInputElement>) {
    onWorksheetChange(event.target.files?.[0] ?? null);
  }

  return (
    <section className="panel call-stage-panel">
      <div className="section-heading">
        <p className="eyebrow">Live Stage</p>
        <h2>Camera, worksheet, and call controls</h2>
      </div>
      <p className="section-copy">
        Set up media once, then keep this panel open while tutoring turns stream into the large
        transcript window.
      </p>

      <div className="call-tiles">
        <article className="call-tile">
          <p className="call-tile-label">Learner camera</p>
          {cameraStream ? (
            <video autoPlay className="camera-preview" muted playsInline ref={cameraVideoRef} />
          ) : (
            <div className="preview-placeholder call-placeholder">
              Camera preview appears here after enabling video.
            </div>
          )}
        </article>

        <article className="call-tile">
          <p className="call-tile-label">Passage / worksheet</p>
          {worksheetPreviewUrl ? (
            <div className="preview-frame">
              <img alt="Worksheet preview" src={worksheetPreviewUrl} />
            </div>
          ) : (
            <div className="preview-placeholder call-placeholder">
              Upload a worksheet image for multimodal tutoring context.
            </div>
          )}
        </article>
      </div>

      <div className="media-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            void onRequestMicrophone();
          }}
        >
          {busyKind === "microphone"
            ? "Checking microphone..."
            : microphoneReady
              ? "Microphone ready"
              : "Enable microphone"}
        </button>
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            void onRequestCamera();
          }}
        >
          {busyKind === "camera" ? "Checking camera..." : cameraReady ? "Camera ready" : "Enable camera"}
        </button>
        <label className="upload-field inline-upload-field">
          <span>Worksheet image</span>
          <input accept="image/*" type="file" onChange={handleWorksheetSelection} />
        </label>
      </div>

      <div className="chip-row">
        <span className={microphoneReady ? "chip chip-ok" : "chip"}>Microphone</span>
        <span className={cameraReady ? "chip chip-ok" : "chip"}>Camera</span>
        <span className={worksheetAttached ? "chip chip-ok" : "chip"}>Worksheet</span>
        <span className={supportsMediaDevices ? "chip chip-ok" : "chip"}>Browser media APIs</span>
      </div>

      {worksheetName ? <p className="small-note">Selected image: {worksheetName}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}
