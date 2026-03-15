import type { ChangeEventHandler } from "react";

import type { LiveConnectionState } from "../hooks/useLiveAgent";

interface LiveControlTrayProps {
  cameraReady: boolean;
  connectionState: LiveConnectionState;
  microphoneActive: boolean;
  microphoneLevel: number;
  onClearTranscript: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onStartMicrophone: () => void;
  onStopMicrophone: () => void;
  onToggleCamera: () => void;
  onWorksheetChange: ChangeEventHandler<HTMLInputElement>;
  sessionReady: boolean;
  worksheetAttached: boolean;
}

export function LiveControlTray({
  cameraReady,
  connectionState,
  microphoneActive,
  microphoneLevel,
  onClearTranscript,
  onConnect,
  onDisconnect,
  onStartMicrophone,
  onStopMicrophone,
  onToggleCamera,
  onWorksheetChange,
  sessionReady,
  worksheetAttached,
}: LiveControlTrayProps) {
  const liveConnected = connectionState === "connected";
  const liveConnecting = connectionState === "connecting";

  return (
    <section className="panel live-control-tray">
      <div className="tray-cluster">
        <button
          className="tray-button tray-button-primary"
          disabled={!sessionReady || liveConnected || liveConnecting}
          type="button"
          onClick={onConnect}
        >
          Join live
        </button>
        <button
          className="tray-button"
          disabled={!liveConnected}
          type="button"
          onClick={onDisconnect}
        >
          Leave live
        </button>
      </div>

      <div className="tray-cluster">
        <button
          className={microphoneActive ? "tray-button tray-button-danger" : "tray-button"}
          disabled={!liveConnected}
          type="button"
          onClick={microphoneActive ? onStopMicrophone : onStartMicrophone}
        >
          {microphoneActive ? "Stop mic turn" : "Start mic turn"}
        </button>
        <div className="mic-meter" aria-hidden="true">
          <span className="mic-meter-fill" style={{ width: `${Math.min(100, microphoneLevel * 100)}%` }} />
        </div>
      </div>

      <div className="tray-cluster">
        <button className="tray-button" type="button" onClick={onToggleCamera}>
          {cameraReady ? "Camera off" : "Camera on"}
        </button>
        <label className="tray-button tray-file-button">
          {worksheetAttached ? "Replace worksheet" : "Add worksheet"}
          <input accept="image/*" hidden type="file" onChange={onWorksheetChange} />
        </label>
        <button className="tray-button" type="button" onClick={onClearTranscript}>
          Clear transcript
        </button>
      </div>
    </section>
  );
}
