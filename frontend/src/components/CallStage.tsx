import { useEffect, useRef } from "react";

import type { LiveConnectionState } from "../hooks/useLiveAgent";
import type { SessionBootstrapResponse } from "../types";

interface CallStageProps {
  cameraStream: MediaStream | null;
  connectionDetail: string;
  connectionState: LiveConnectionState;
  microphoneActive: boolean;
  session: SessionBootstrapResponse | null;
  worksheetName: string | null;
  worksheetPreviewUrl: string | null;
}

export function CallStage({
  cameraStream,
  connectionDetail,
  connectionState,
  microphoneActive,
  session,
  worksheetName,
  worksheetPreviewUrl,
}: CallStageProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = cameraStream;
    }
  }, [cameraStream]);

  return (
    <section className="panel stage-panel">
      <div className="section-heading">
        <p className="eyebrow">Live Console</p>
        <h2>Call-stage workspace</h2>
      </div>

      <div className="call-stage-grid">
        <article className="call-surface call-surface-primary">
          <header className="surface-label-row">
            <span className="surface-label">Learner camera</span>
            <span className={cameraStream ? "chip chip-ok" : "chip"}>
              {cameraStream ? "Camera live" : "Camera off"}
            </span>
          </header>

          {cameraStream ? (
            <video
              ref={videoRef}
              className="call-video"
              autoPlay
              muted
              playsInline
            />
          ) : (
            <div className="call-empty-state">
              Camera preview will appear here when you turn the camera on.
            </div>
          )}
        </article>

        <article className="call-surface tutor-surface">
          <header className="surface-label-row">
            <span className="surface-label">Tutor channel</span>
            <span className={connectionState === "connected" ? "chip chip-ok" : "chip"}>
              {connectionState}
            </span>
          </header>

          <div className="tutor-surface-copy">
            <h3>Ancient Greek Live Tutor</h3>
            <p>{session ? session.mode_goal : "Start a session to load the tutor mode and prompt."}</p>
            <dl className="stage-metadata">
              <div>
                <dt>Mode</dt>
                <dd>{session?.mode_label ?? "Not started"}</dd>
              </div>
              <div>
                <dt>Focus</dt>
                <dd>{session?.session_state.active_focus ?? "Awaiting bootstrap"}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{connectionDetail}</dd>
              </div>
              <div>
                <dt>Mic</dt>
                <dd>{microphoneActive ? "Streaming voice turn" : "Idle"}</dd>
              </div>
            </dl>
          </div>
        </article>

        <article className="call-surface call-surface-secondary">
          <header className="surface-label-row">
            <span className="surface-label">Worksheet or passage image</span>
            <span className={worksheetPreviewUrl ? "chip chip-ok" : "chip"}>
              {worksheetPreviewUrl ? "Attached" : "None"}
            </span>
          </header>

          {worksheetPreviewUrl ? (
            <div className="worksheet-preview-shell">
              <img alt={worksheetName ?? "Worksheet preview"} src={worksheetPreviewUrl} />
              <p>{worksheetName}</p>
            </div>
          ) : (
            <div className="call-empty-state">
              Add a worksheet image to keep visual context alongside the call.
            </div>
          )}
        </article>
      </div>
    </section>
  );
}

