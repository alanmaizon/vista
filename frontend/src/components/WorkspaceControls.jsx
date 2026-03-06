import { useState } from "react";
import {
  Camera,
  CameraOff,
  ChevronDown,
  LoaderCircle,
  MessageCircle,
  Mic,
  MicOff,
  PauseCircle,
  PlayCircle,
  Radio,
  ScanLine,
  Sparkles,
} from "lucide-react";

const WORKSPACE_CAPABILITIES = [
  "Live conversation and lesson prompting",
  "Focused phrase capture and deterministic analysis",
  "Camera score reading for one bar at a time",
];

const GUIDE_PROMPTS = {
  idle: "Start Session when you want Gemini Live to join the studio.",
  starting: "Starting the live tutor. Microphone routing will open after the session is ready.",
  connected: "The tutor is live. Speak naturally, or use the lesson controls when you are ready.",
  busy: "A lesson action is running. Wait for it to finish before starting another.",
};

function resolveGuideMessage({ isConnected, isBusy, isSessionStarting, runtimeSummary }) {
  if (isBusy) {
    return GUIDE_PROMPTS.busy;
  }
  if (isSessionStarting) {
    return GUIDE_PROMPTS.starting;
  }
  if (isConnected) {
    return runtimeSummary || GUIDE_PROMPTS.connected;
  }
  return GUIDE_PROMPTS.idle;
}

export default function WorkspaceControls({
  authStatus,
  micEnabled,
  cameraEnabled,
  instrumentProfile,
  isConnected,
  liveMode,
  liveAudioMode,
  status,
  runtimeSummary,
  sessionId,
  isReadingScore,
  isBusy,
  isSessionStarting,
  primaryActionLabel,
  onToggleMic,
  onToggleCamera,
  onInstrumentProfileChange,
  onStartTutorSession,
  onStopTutorSession,
  onPrimaryAction,
  onCapturePhrase,
  onToggleScoreReader,
}) {
  const [showActions, setShowActions] = useState(false);
  const guideMessage = resolveGuideMessage({ isConnected, isBusy, isSessionStarting, runtimeSummary });
  const guidedSessionActive = isConnected && liveMode === "GUIDED_LESSON";
  const lessonControlsEnabled = guidedSessionActive && !isSessionStarting;

  return (
    <aside className="glass rounded-[2.2rem] p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-white">
          <Sparkles className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Live tutor
          </div>
          <div className="mt-0.5 text-xs text-slate-500">{status}</div>
        </div>
      </div>

      <div className="mt-4 rounded-[1.8rem] border border-slate-300 bg-[#f8f9fb] px-4 py-4">
        <div className="flex items-start gap-3">
          <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-700" />
          <p className="text-sm leading-relaxed text-slate-700">{guideMessage}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={guidedSessionActive ? onStopTutorSession : onStartTutorSession}
        disabled={isSessionStarting || (isBusy && !guidedSessionActive)}
        className="mt-4 flex w-full min-h-13 items-center justify-center gap-2 rounded-[1.5rem] bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"
      >
        {isSessionStarting ? (
          <LoaderCircle className="h-4 w-4 animate-spin" />
        ) : guidedSessionActive ? (
          <PauseCircle className="h-4 w-4" />
        ) : (
          <PlayCircle className="h-4 w-4" />
        )}
        {isSessionStarting ? "Starting session..." : guidedSessionActive ? "Stop session" : "Start session"}
      </button>

      <button
        type="button"
        onClick={onPrimaryAction}
        disabled={!lessonControlsEnabled || isBusy}
        className="mt-4 flex w-full min-h-14 items-center justify-center gap-2 rounded-[1.6rem] border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-55"
      >
        {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />}
        {primaryActionLabel}
      </button>

      {!lessonControlsEnabled ? (
        <div className="mt-2 text-xs leading-relaxed text-slate-500">
          Start Session first. Guided lesson tools no longer auto-open Gemini Live implicitly.
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-[1.4rem] border border-slate-300 bg-white px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Live mode
          </div>
          <div className="mt-2 text-sm font-medium text-slate-900">{liveMode || "closed"}</div>
        </div>
        <div className="rounded-[1.4rem] border border-slate-300 bg-white px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Audio route
          </div>
          <div className="mt-2 text-sm font-medium text-slate-900">{liveAudioMode}</div>
        </div>
      </div>

      <div className="mt-3">
        <button
          type="button"
          onClick={() => setShowActions((value) => !value)}
          className="flex w-full items-center justify-between gap-2 rounded-[1.4rem] border border-slate-300 bg-white px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-50"
        >
          Secondary actions
          <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${showActions ? "rotate-180" : ""}`} />
        </button>

        {showActions ? (
          <div className="mt-3 grid gap-2">
            <button
              type="button"
              onClick={onCapturePhrase}
              disabled={isBusy || isSessionStarting}
              className="flex items-center justify-center gap-2 rounded-[1.4rem] border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
            >
              <Mic className="h-4 w-4" />
              Capture phrase
            </button>
            <button
              type="button"
              onClick={onToggleScoreReader}
              disabled={isBusy || isSessionStarting}
              className="flex items-center justify-center gap-2 rounded-[1.4rem] border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
            >
              <ScanLine className="h-4 w-4" />
              {isReadingScore ? "Stop reader" : "Read from camera"}
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={onToggleMic}
                className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-3 py-2.5 text-xs font-medium transition ${
                  micEnabled ? "bg-emerald-50 text-emerald-700" : "bg-white text-slate-500"
                }`}
              >
                {micEnabled ? <Mic className="h-3.5 w-3.5" /> : <MicOff className="h-3.5 w-3.5" />}
                Mic
              </button>
              <button
                type="button"
                onClick={onToggleCamera}
                className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-3 py-2.5 text-xs font-medium transition ${
                  cameraEnabled ? "bg-slate-900 text-white" : "bg-white text-slate-500"
                }`}
              >
                {cameraEnabled ? <Camera className="h-3.5 w-3.5" /> : <CameraOff className="h-3.5 w-3.5" />}
                Camera
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <details className="mt-4 rounded-[1.8rem] border border-slate-300 bg-white px-4 py-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          <span>Studio onboarding</span>
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </summary>

        <div className="mt-4 space-y-3">
          {WORKSPACE_CAPABILITIES.map((item) => (
            <div key={item} className="rounded-[1.3rem] border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-600">
              {item}
            </div>
          ))}
        </div>
      </details>

      <details className="mt-4 rounded-[1.8rem] border border-slate-300 bg-white px-4 py-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          <span>Session tuning</span>
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </summary>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Instrument profile
            </label>
            <select
              value={instrumentProfile}
              onChange={(event) => onInstrumentProfileChange(event.target.value)}
              className="mt-2 w-full rounded-[1.4rem] border border-slate-300 bg-[#f8f9fb] px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-500"
            >
              <option value="AUTO">Auto (generic)</option>
              <option value="PIANO">Piano / keys</option>
              <option value="GUITAR">Guitar</option>
              <option value="STRINGS">Strings</option>
              <option value="WINDS">Winds</option>
              <option value="VOICE">Voice</option>
              <option value="PERCUSSION">Percussion</option>
            </select>
          </div>

          <div className="rounded-[1.4rem] border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-xs text-slate-500">
            <div className="font-semibold uppercase tracking-[0.14em] text-slate-600">Identity</div>
            <div className="mt-2 break-all">{authStatus}</div>
            {sessionId ? <div className="mt-2">Session: {sessionId}</div> : null}
          </div>
        </div>
      </details>
    </aside>
  );
}
