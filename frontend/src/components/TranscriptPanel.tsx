import type { SessionBootstrapResponse } from "../types";

interface TranscriptPanelProps {
  session: SessionBootstrapResponse | null;
}

export function TranscriptPanel({ session }: TranscriptPanelProps) {
  const rows = session
    ? [
        "Assistant audio transcript will appear here after the Gemini Live bridge is wired in.",
        "Learner turns will appear here after microphone chunks are streamed to the live session.",
        `Current focus: ${session.session_state.active_focus}`,
      ]
    : [
        "No active session yet.",
        "This area is reserved for learner and tutor transcript turns.",
      ];

  return (
    <section className="panel">
      <div className="section-heading">
        <p className="eyebrow">Transcript</p>
        <h2>Live turns and status messages</h2>
      </div>
      <div className="transcript-stack">
        {rows.map((row) => (
          <div className="transcript-row" key={row}>
            <span className="transcript-label">placeholder</span>
            <p>{row}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

