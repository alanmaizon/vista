import type { ChangeEvent } from "react";

interface MediaPrepCardProps {
  busyKind: "microphone" | "camera" | null;
  cameraReady: boolean;
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
  function handleWorksheetSelection(event: ChangeEvent<HTMLInputElement>) {
    onWorksheetChange(event.target.files?.[0] ?? null);
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <p className="eyebrow">Media Prep</p>
        <h2>Prepare the live inputs</h2>
      </div>
      <p className="section-copy">
        This scaffold asks for permissions early so microphone, camera, or worksheet intake can
        be wired into a live session without reshaping the UI later.
      </p>

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
      </div>

      <label className="upload-field">
        <span>Worksheet image</span>
        <input accept="image/*" type="file" onChange={handleWorksheetSelection} />
      </label>

      <div className="chip-row">
        <span className={microphoneReady ? "chip chip-ok" : "chip"}>Microphone</span>
        <span className={cameraReady ? "chip chip-ok" : "chip"}>Camera</span>
        <span className={worksheetAttached ? "chip chip-ok" : "chip"}>Worksheet</span>
        <span className={supportsMediaDevices ? "chip chip-ok" : "chip"}>Browser media APIs</span>
      </div>

      {worksheetName ? <p className="small-note">Selected image: {worksheetName}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {worksheetPreviewUrl ? (
        <div className="preview-frame">
          <img alt="Worksheet preview" src={worksheetPreviewUrl} />
        </div>
      ) : (
        <div className="preview-placeholder">
          Camera frames or uploaded worksheet previews will appear here.
        </div>
      )}
    </section>
  );
}

