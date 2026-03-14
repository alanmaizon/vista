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
import {
  actionLabelFromKey,
  normalizeLessonPhase,
  resolveVisibleControls,
} from "../lib/lessonFlow";

const WORKSPACE_CAPABILITIES = [
  "Live tutor on demand",
  "Capture, compare, fix",
  "Camera reads one bar",
];

const GUIDE_PROMPTS = {
  idle: "Start Session to bring Gemini in.",
  starting: "Opening the live tutor.",
  connected: "Tutor is live. Speak or run the next step.",
  busy: "One lesson action is running.",
};

function resolveGuideMessage({ isConnected, isBusy, isSessionStarting, runtimeSummary, lessonStatus }) {
  if (isBusy) {
    return GUIDE_PROMPTS.busy;
  }
  if (isSessionStarting) {
    return GUIDE_PROMPTS.starting;
  }
  if (isConnected && lessonStatus) {
    return lessonStatus;
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
  lessonFlow,
  onToggleMic,
  onToggleCamera,
  onInstrumentProfileChange,
  onStartTutorSession,
  onStopTutorSession,
  onPrimaryAction,
  onCapturePhrase,
  onToggleScoreReader,
  onRunRecommendedAction,
}) {
  const [showActions, setShowActions] = useState(false);
  const guidedSessionActive = isConnected && liveMode === "GUIDED_LESSON";
  const lessonPhase = normalizeLessonPhase(lessonFlow?.phase);
  const lessonStatus = typeof lessonFlow?.status === "string" ? lessonFlow.status : "";
  const suggestedActions = Array.isArray(lessonFlow?.suggestedActions)
    ? lessonFlow.suggestedActions.filter(Boolean)
    : [];
  const visibleControls = resolveVisibleControls({ phase: lessonPhase, guidedSessionActive });
  const guideMessage = resolveGuideMessage({
    isConnected,
    isBusy,
    isSessionStarting,
    runtimeSummary,
    lessonStatus,
  });
  const lessonControlsEnabled = guidedSessionActive && !isSessionStarting;

  return (
    <aside className="glass border border-slate-300/90 p-4 shadow-[0_18px_38px_rgba(47,52,58,0.05)]">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center bg-slate-900 text-white">
          <Sparkles className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Live tutor
          </div>
          <div className="mt-0.5 text-xs text-slate-500">{status}</div>
        </div>
      </div>

      <div className="mt-4 border border-slate-300 bg-[#f8f9fb] px-4 py-4">
        <div className="flex items-start gap-3">
          <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-700" />
          <p className="text-sm text-slate-700">{guideMessage}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={guidedSessionActive ? onStopTutorSession : onStartTutorSession}
        disabled={isSessionStarting || (isBusy && !guidedSessionActive)}
        className="mt-4 flex w-full min-h-13 items-center justify-center gap-2 border border-slate-900 bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px] hover:bg-slate-800 hover:shadow-[12px_12px_0_rgba(47,52,58,0.18)] disabled:cursor-wait disabled:opacity-70"
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

      {visibleControls.showPrimaryAction ? (
        <button
          type="button"
          onClick={onPrimaryAction}
          disabled={!lessonControlsEnabled || isBusy}
          className="mt-4 flex w-full min-h-14 items-center justify-center gap-2 border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900 shadow-[8px_8px_0_rgba(184,189,197,0.24)] transition hover:-translate-x-[2px] hover:-translate-y-[2px] hover:bg-slate-50 hover:shadow-[12px_12px_0_rgba(184,189,197,0.32)] disabled:cursor-not-allowed disabled:opacity-55"
        >
          {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />}
          {primaryActionLabel}
        </button>
      ) : null}

      {!lessonControlsEnabled || !visibleControls.showPrimaryAction ? (
        <div className="mt-2 text-xs text-slate-500">
          {guidedSessionActive
            ? "Controls appear when this phase needs them."
            : "Start Session first."}
        </div>
      ) : null}

      {guidedSessionActive && suggestedActions.length ? (
        <div className="mt-3 border border-slate-300 bg-white px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Next
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestedActions.slice(0, 3).map((action) => (
              <button
                key={action}
                type="button"
                onClick={() => onRunRecommendedAction?.(action)}
                className="border border-slate-300 bg-[#f8f9fb] px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
              >
                {actionLabelFromKey(action)}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="border border-slate-300 bg-white px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Mode
          </div>
          <div className="mt-2 text-sm font-medium text-slate-900">{liveMode || "closed"}</div>
        </div>
        <div className="border border-slate-300 bg-white px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Audio
          </div>
          <div className="mt-2 text-sm font-medium text-slate-900">{liveAudioMode}</div>
        </div>
      </div>

      {visibleControls.showSecondaryToggle ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowActions((value) => !value)}
            className="flex w-full items-center justify-between gap-2 border border-slate-300 bg-white px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-50"
          >
            Extra actions
            <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${showActions ? "rotate-180" : ""}`} />
          </button>

          {showActions ? (
            <div className="mt-3 grid gap-2">
              {visibleControls.showCapturePhrase ? (
                <button
                  type="button"
                  onClick={onCapturePhrase}
                  disabled={isBusy || isSessionStarting}
                  className="flex items-center justify-center gap-2 border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
                >
                  <Mic className="h-4 w-4" />
                  Capture phrase
                </button>
              ) : null}
              {visibleControls.showScoreReader ? (
                <button
                  type="button"
                  onClick={onToggleScoreReader}
                  disabled={isBusy || isSessionStarting}
                  className="flex items-center justify-center gap-2 border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
                >
                  <ScanLine className="h-4 w-4" />
                  {isReadingScore ? "Stop reader" : "Read from camera"}
                </button>
              ) : null}
              {visibleControls.showInputToggles ? (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={onToggleMic}
                    className={`flex items-center justify-center gap-2 border px-3 py-2.5 text-xs font-medium transition ${
                      micEnabled
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-slate-300 bg-white text-slate-500"
                    }`}
                  >
                    {micEnabled ? <Mic className="h-3.5 w-3.5" /> : <MicOff className="h-3.5 w-3.5" />}
                    Mic
                  </button>
                  <button
                    type="button"
                    onClick={onToggleCamera}
                    className={`flex items-center justify-center gap-2 border px-3 py-2.5 text-xs font-medium transition ${
                      cameraEnabled
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-300 bg-white text-slate-500"
                    }`}
                  >
                    {cameraEnabled ? <Camera className="h-3.5 w-3.5" /> : <CameraOff className="h-3.5 w-3.5" />}
                    Camera
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <details className="mt-4 border border-slate-300 bg-white px-4 py-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          <span>Workspace notes</span>
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </summary>

        <div className="mt-4 space-y-3">
          {WORKSPACE_CAPABILITIES.map((item) => (
            <div key={item} className="border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-600">
              {item}
            </div>
          ))}
        </div>
      </details>

      <details className="mt-4 border border-slate-300 bg-white px-4 py-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          <span>Tuning</span>
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
              className="mt-2 w-full border border-slate-300 bg-[#f8f9fb] px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-500"
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

          <div className="border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-xs text-slate-500">
            <div className="font-semibold uppercase tracking-[0.14em] text-slate-600">Identity</div>
            <div className="mt-2 break-all">{authStatus}</div>
            {sessionId ? <div className="mt-2">Session: {sessionId}</div> : null}
          </div>
        </div>
      </details>
    </aside>
  );
}
