import type { RuntimeSnapshot, SessionBootstrapResponse } from "../types";

interface StatusPanelProps {
  runtime: RuntimeSnapshot | null;
  runtimeError: string | null;
  runtimeLoading: boolean;
  session: SessionBootstrapResponse | null;
}

export function StatusPanel({
  runtime,
  runtimeError,
  runtimeLoading,
  session,
}: StatusPanelProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <p className="eyebrow">Runtime</p>
        <h2>Backend and session status</h2>
      </div>

      <div className="status-grid">
        <div className="status-item">
          <span>Service</span>
          <strong>{runtime?.service_name ?? (runtimeLoading ? "Loading..." : "Unavailable")}</strong>
        </div>
        <div className="status-item">
          <span>Environment</span>
          <strong>{runtime?.environment ?? "unknown"}</strong>
        </div>
        <div className="status-item">
          <span>WebSocket</span>
          <strong>{session?.live_session.websocket_path ?? runtime?.websocket_path ?? "/ws/live"}</strong>
        </div>
        <div className="status-item">
          <span>Model</span>
          <strong>{session?.live_session.model ?? "Gemini model pending"}</strong>
        </div>
      </div>

      <div className="chip-row">
        <span className={runtime?.google_adk_available ? "chip chip-ok" : "chip"}>
          ADK {runtime?.google_adk_available ? "available" : "pending"}
        </span>
        <span className={runtime?.google_genai_available ? "chip chip-ok" : "chip"}>
          GenAI SDK {runtime?.google_genai_available ? "available" : "pending"}
        </span>
        <span className={session ? "chip chip-ok" : "chip"}>{session ? "Session seeded" : "No live session"}</span>
      </div>

      {runtimeError ? <p className="error-text">{runtimeError}</p> : null}

      {session ? (
        <>
          <p className="section-copy">{session.live_session.notes}</p>
          <ul className="plain-list">
            {session.next_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="section-copy">
          The runtime panel will expand once the backend is running and a session bootstrap is created.
        </p>
      )}
    </section>
  );
}

