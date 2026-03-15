import { useDeferredValue, useState } from "react";
import type { FormEvent } from "react";

import type { LiveConnectionState, TranscriptEntry } from "../hooks/useLiveAgent";
import type { SessionBootstrapResponse } from "../types";

interface TranscriptPanelProps {
  connectionDetail: string;
  connectionError: string | null;
  connectionState: LiveConnectionState;
  onClearTranscript: () => void;
  onSendTextTurn: (text: string) => boolean;
  session: SessionBootstrapResponse | null;
  transcriptEntries: TranscriptEntry[];
}

const CONNECTION_LABELS: Record<LiveConnectionState, string> = {
  idle: "Offline",
  connecting: "Connecting",
  connected: "Live",
  error: "Error",
};

export function TranscriptPanel({
  connectionDetail,
  connectionError,
  connectionState,
  onClearTranscript,
  onSendTextTurn,
  session,
  transcriptEntries,
}: TranscriptPanelProps) {
  const [draftText, setDraftText] = useState("");
  const deferredEntries = useDeferredValue(transcriptEntries);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draftText.trim()) {
      return;
    }
    const sent = onSendTextTurn(draftText);
    if (sent) {
      setDraftText("");
    }
  }

  return (
    <section className="panel transcript-panel-large">
      <div className="section-heading transcript-heading">
        <div>
          <p className="eyebrow">Transcript</p>
          <h2>Live tutoring dialog</h2>
          <p className="section-copy transcript-summary">
            {session
              ? `Mode: ${session.mode_label}. Focus: ${session.session_state.active_focus}`
              : "Start a tutor session to unlock live websocket controls."}
          </p>
        </div>
        <div className="transcript-controls">
          <span
            className={connectionState === "connected" ? "chip chip-ok state-chip" : "chip state-chip"}
          >
            {CONNECTION_LABELS[connectionState]}
          </span>
          <button className="secondary-button" type="button" onClick={onClearTranscript}>
            Clear
          </button>
        </div>
      </div>

      <p className="small-note">{connectionDetail}</p>
      {connectionError ? <p className="error-text">{connectionError}</p> : null}

      <div className="transcript-feed">
        {deferredEntries.length > 0 ? (
          deferredEntries.map((entry) => (
            <article
              className={`transcript-bubble transcript-bubble-${entry.speaker}`}
              key={entry.id}
            >
              <span className="transcript-label">{entry.speaker}</span>
              <p>{entry.text}</p>
            </article>
          ))
        ) : (
          <div className="transcript-empty">
            {session
              ? "No transcript lines yet. Join live, then send a learner line to begin."
              : "No active session yet."}
          </div>
        )}
      </div>

      <form className="transcript-composer" onSubmit={handleSubmit}>
        <label>
          <span className="sr-only">Send learner text</span>
          <textarea
            disabled={connectionState !== "connected"}
            placeholder={
              connectionState === "connected"
                ? "Type a learner line and send it as a live turn..."
                : "Join live to send text turns."
            }
            rows={3}
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
          />
        </label>
        <button className="primary-button" disabled={connectionState !== "connected"} type="submit">
          Send turn
        </button>
      </form>
    </section>
  );
}
