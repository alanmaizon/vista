import type { FormEventHandler } from "react";

import type {
  ModeSummary,
  SessionBootstrapResponse,
  SessionDraft,
} from "../types";

interface SessionComposerProps {
  draft: SessionDraft;
  isLoading: boolean;
  isStarting: boolean;
  modes: ModeSummary[];
  onChange: (field: keyof SessionDraft, value: string) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  session: SessionBootstrapResponse | null;
  sessionError: string | null;
}

export function SessionComposer({
  draft,
  isLoading,
  isStarting,
  modes,
  onChange,
  onSubmit,
  session,
  sessionError,
}: SessionComposerProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <p className="eyebrow">Tutor Session</p>
        <h2>Seed the first live session</h2>
      </div>
      <p className="section-copy">
        The form mirrors the backend bootstrap payload so we can grow from scaffold to real live
        session flow without reworking the UI contract.
      </p>

      <form className="session-form" onSubmit={onSubmit}>
        <label>
          <span>Learner name</span>
          <input
            type="text"
            value={draft.learnerName}
            onChange={(event) => onChange("learnerName", event.target.value)}
          />
        </label>

        <label>
          <span>Tutoring mode</span>
          <select
            value={draft.mode}
            onChange={(event) => onChange("mode", event.target.value)}
          >
            {modes.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Target passage or exercise prompt</span>
          <textarea
            placeholder="Paste a short Ancient Greek passage or describe the worksheet focus."
            rows={6}
            value={draft.targetText}
            onChange={(event) => onChange("targetText", event.target.value)}
          />
        </label>

        <label>
          <span>Response language</span>
          <input
            type="text"
            value={draft.preferredResponseLanguage}
            onChange={(event) => onChange("preferredResponseLanguage", event.target.value)}
          />
        </label>

        <button className="primary-button" disabled={isLoading || isStarting} type="submit">
          {isStarting ? "Starting session..." : "Start scaffold session"}
        </button>
      </form>

      {sessionError ? <p className="error-text">{sessionError}</p> : null}
      {session ? (
        <div className="success-box">
          <strong>{session.mode_label} ready.</strong>
          <p>{session.mode_goal}</p>
        </div>
      ) : null}
    </section>
  );
}

