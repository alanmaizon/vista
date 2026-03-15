import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import { CallStage } from "./components/CallStage";
import { LiveControlTray } from "./components/LiveControlTray";
import { MorphologyPanel } from "./components/MorphologyPanel";
import { SessionComposer } from "./components/SessionComposer";
import { StatusPanel } from "./components/StatusPanel";
import { TranscriptPanel } from "./components/TranscriptPanel";
import { useLiveAgent } from "./hooks/useLiveAgent";
import { useMediaPrep } from "./hooks/useMediaPrep";
import { AudioRecorder } from "./lib/live-audio/AudioRecorder";
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

export default function App() {
  const [draft, setDraft] = useState<SessionDraft>(initialDraft);
  const [modes, setModes] = useState<ModeSummary[]>(fallbackModes);
  const [runtime, setRuntime] = useState<RuntimeSnapshot | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(true);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [session, setSession] = useState<SessionBootstrapResponse | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [microphoneReady, setMicrophoneReady] = useState(false);
  const [microphoneActive, setMicrophoneActive] = useState(false);
  const [microphoneLevel, setMicrophoneLevel] = useState(0);
  const [liveActionError, setLiveActionError] = useState<string | null>(null);

  const media = useMediaPrep();
  const live = useLiveAgent({
    preferredResponseLanguage: draft.preferredResponseLanguage,
    session,
  });
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const audioTurnRef = useRef<{
    turnId: string;
    chunkIndex: number;
    sentAnyChunks: boolean;
  } | null>(null);

  useEffect(() => {
    void loadBootstrapData();
  }, []);

  useEffect(() => {
    audioRecorderRef.current = new AudioRecorder();

    return () => {
      audioRecorderRef.current?.stop();
      audioRecorderRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (live.connectionState !== "connected" && microphoneActive) {
      stopMicrophoneTurn();
    }
  }, [live.connectionState, microphoneActive]);

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
        microphone_ready: microphoneReady,
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

  async function startMicrophoneTurn() {
    if (live.connectionState !== "connected") {
      setLiveActionError("Join live before starting a microphone turn.");
      return;
    }

    const recorder = audioRecorderRef.current;
    if (!recorder) {
      setLiveActionError("Microphone recorder is not ready.");
      return;
    }

    const turnId = live.createTurnId("turn-voice");
    audioTurnRef.current = {
      turnId,
      chunkIndex: 0,
      sentAnyChunks: false,
    };

    recorder.onData = (dataBase64: string) => {
      const currentTurn = audioTurnRef.current;
      if (!currentTurn) {
        return;
      }

      const sent = live.sendAudioChunk({
        turnId: currentTurn.turnId,
        chunkIndex: currentTurn.chunkIndex,
        dataBase64,
      });

      if (sent) {
        currentTurn.chunkIndex += 1;
        currentTurn.sentAnyChunks = true;
      }
    };

    recorder.onVolume = (volume: number) => {
      setMicrophoneLevel(volume);
    };

    try {
      setLiveActionError(null);
      await recorder.start();
      setMicrophoneReady(true);
      setMicrophoneActive(true);
    } catch (error) {
      audioTurnRef.current = null;
      recorder.stop();
      recorder.onData = null;
      recorder.onVolume = null;
      setMicrophoneActive(false);
      setMicrophoneLevel(0);
      setLiveActionError(
        error instanceof Error ? error.message : "Unable to start microphone capture.",
      );
    }
  }

  function stopMicrophoneTurn() {
    const recorder = audioRecorderRef.current;
    recorder?.stop();
    if (recorder) {
      recorder.onData = null;
      recorder.onVolume = null;
    }

    const completedTurn = audioTurnRef.current;
    audioTurnRef.current = null;
    setMicrophoneActive(false);
    setMicrophoneLevel(0);

    if (completedTurn?.sentAnyChunks) {
      live.endTurn(completedTurn.turnId, "stop_recording");
    }
  }

  async function handleToggleCamera() {
    setLiveActionError(null);

    if (media.cameraReady) {
      media.stopCamera();
      return;
    }

    await media.requestCamera();
  }

  function handleWorksheetChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    media.setWorksheet(file);
    event.target.value = "";
  }

  function handleConnect() {
    setLiveActionError(null);
    live.connect();
  }

  function handleDisconnect() {
    stopMicrophoneTurn();
    live.disconnect();
  }

  const transcriptError = liveActionError ?? media.error ?? live.connectionError;

  return (
    <div className="app-shell">
      <header className="call-header">
        <div>
          <p className="eyebrow">Gemini Live Console</p>
          <h1>Ancient Greek Live Tutor</h1>
          <p className="hero-copy">
            Official-console-inspired live tutoring workspace, adapted to our backend websocket and
            session-based agent context.
          </p>
        </div>
        <div className="call-header-meta">
          <span className={session ? "chip chip-ok" : "chip"}>
            {session ? session.mode_label : "Session not started"}
          </span>
          <span className={live.connectionState === "connected" ? "chip chip-ok" : "chip"}>
            Live agent: {live.connectionState}
          </span>
        </div>
      </header>

      <main className="console-layout">
        <aside className="console-sidebar">
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
        </aside>

        <section className="console-main">
          <CallStage
            cameraStream={media.cameraStream}
            connectionDetail={live.connectionDetail}
            connectionState={live.connectionState}
            microphoneActive={microphoneActive}
            session={session}
            worksheetName={media.worksheetName}
            worksheetPreviewUrl={media.worksheetPreviewUrl}
          />

          <LiveControlTray
            cameraReady={media.cameraReady}
            connectionState={live.connectionState}
            microphoneActive={microphoneActive}
            microphoneLevel={microphoneLevel}
            onClearTranscript={live.clearTranscript}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            onStartMicrophone={startMicrophoneTurn}
            onStopMicrophone={stopMicrophoneTurn}
            onToggleCamera={() => void handleToggleCamera()}
            onWorksheetChange={handleWorksheetChange}
            sessionReady={Boolean(session)}
            worksheetAttached={media.worksheetAttached}
          />

          <TranscriptPanel
            connectionDetail={live.connectionDetail}
            connectionError={transcriptError}
            connectionState={live.connectionState}
            onClearTranscript={live.clearTranscript}
            onSendTextTurn={live.sendTextTurn}
            session={session}
            transcriptEntries={live.transcriptEntries}
          />
        </section>
      </main>
    </div>
  );
}
