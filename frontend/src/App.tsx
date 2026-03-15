import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { MediaPrepCard } from "./components/MediaPrepCard";
import { MorphologyPanel } from "./components/MorphologyPanel";
import { SessionComposer } from "./components/SessionComposer";
import { StatusPanel } from "./components/StatusPanel";
import { TranscriptPanel } from "./components/TranscriptPanel";
import { useLiveAgent } from "./hooks/useLiveAgent";
import { useMediaPrep } from "./hooks/useMediaPrep";
import { getModes, getRuntime, startSession } from "./lib/api";
import type {
  ModeSummary,
  RuntimeSnapshot,
  SessionBootstrapResponse,
  SessionDraft,
  TutorMode,
} from "./types";

const fallbackModes: ModeSummary[] = [
  {
    value: "guided_reading",
    label: "Guided Reading",
    goal: "Help the learner read a short passage aloud and stay oriented in the syntax.",
    first_turn: "Invite the learner to read one clause aloud.",
  },
  {
    value: "morphology_coach",
    label: "Morphology Coach",
    goal: "Coach endings, stems, and inflection choices without jumping to a full translation.",
    first_turn: "Ask which form is blocking the learner.",
  },
  {
    value: "translation_support",
    label: "Translation Support",
    goal: "Guide the learner toward a defensible translation with hints.",
    first_turn: "Request the learner's rough translation.",
  },
  {
    value: "oral_reading",
    label: "Oral Reading",
    goal: "Support pronunciation, pacing, and chunking for spoken practice.",
    first_turn: "Set a short oral reading target.",
  },
];

const initialDraft: SessionDraft = {
  learnerName: "Learner",
  mode: "guided_reading",
  targetText: "",
  preferredResponseLanguage: "English",
};

function App() {
  const [draft, setDraft] = useState<SessionDraft>(initialDraft);
  const [modes, setModes] = useState<ModeSummary[]>(fallbackModes);
  const [runtime, setRuntime] = useState<RuntimeSnapshot | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(true);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [session, setSession] = useState<SessionBootstrapResponse | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const media = useMediaPrep();
  const live = useLiveAgent({
    preferredResponseLanguage: draft.preferredResponseLanguage,
    session,
  });

  useEffect(() => {
    void loadBootstrapData();
  }, []);

  async function loadBootstrapData() {
    setRuntimeLoading(true);
    setRuntimeError(null);

    try {
      const [runtimeResponse, modesResponse] = await Promise.all([getRuntime(), getModes()]);
      setRuntime(runtimeResponse);
      setModes(modesResponse);
      setDraft((current) => ({
        ...current,
        mode: runtimeResponse.default_mode,
      }));
    } catch (error) {
      setRuntimeError(error instanceof Error ? error.message : "Unable to load backend runtime.");
    } finally {
      setRuntimeLoading(false);
    }
  }

  function updateDraft(field: keyof SessionDraft, value: string) {
    setDraft((current) => ({
      ...current,
      [field]: field === "mode" ? (value as TutorMode) : value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsStarting(true);
    setSessionError(null);

    try {
      const response = await startSession({
        learner_name: draft.learnerName,
        mode: draft.mode,
        target_text: draft.targetText,
        worksheet_attached: media.worksheetAttached,
        microphone_ready: media.microphoneReady,
        camera_ready: media.cameraReady,
        preferred_response_language: draft.preferredResponseLanguage,
      });
      setSession(response);
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Unable to start tutor session.");
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="call-header">
        <div>
          <p className="eyebrow">Scaffold</p>
          <h1>Ancient Greek Live Tutor</h1>
          <p className="hero-copy">
            Video-call style tutoring shell with a large transcript workspace for live coaching.
          </p>
        </div>
        <div className="call-header-meta">
          <span className={live.connectionState === "connected" ? "chip chip-ok" : "chip"}>
            Live agent: {live.connectionState}
          </span>
          <span className={session ? "chip chip-ok" : "chip"}>
            Session: {session ? session.session_id : "not started"}
          </span>
        </div>
      </header>

      <main className="call-layout">
        <div className="call-stage-stack">
          <MediaPrepCard
            busyKind={media.busyKind}
            cameraReady={media.cameraReady}
            cameraStream={media.cameraStream}
            error={media.error}
            microphoneReady={media.microphoneReady}
            onRequestCamera={media.requestCamera}
            onRequestMicrophone={media.requestMicrophone}
            onWorksheetChange={media.setWorksheet}
            supportsMediaDevices={media.supportsMediaDevices}
            worksheetAttached={media.worksheetAttached}
            worksheetName={media.worksheetName}
            worksheetPreviewUrl={media.worksheetPreviewUrl}
          />
          <SessionComposer
            draft={draft}
            isLoading={runtimeLoading}
            isStarting={isStarting}
            modes={modes}
            onChange={updateDraft}
            onSubmit={handleSubmit}
            session={session}
            sessionError={sessionError}
          />
          <StatusPanel
            runtime={runtime}
            runtimeError={runtimeError}
            runtimeLoading={runtimeLoading}
            session={session}
          />
          <MorphologyPanel session={session} />
        </div>

        <TranscriptPanel
          connectionDetail={live.connectionDetail}
          connectionError={live.connectionError}
          connectionState={live.connectionState}
          onClearTranscript={live.clearTranscript}
          onConnect={live.connect}
          onDisconnect={live.disconnect}
          onSendTextTurn={live.sendTextTurn}
          session={session}
          transcriptEntries={live.transcriptEntries}
        />
      </main>
    </div>
  );
}

export default App;
