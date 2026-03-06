import { useState } from "react";
import {
  Camera,
  CameraOff,
  ChevronDown,
  Cpu,
  LoaderCircle,
  MessageCircle,
  Mic,
  MicOff,
  PauseCircle,
  PlayCircle,
  Radio,
  ScanLine,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";

const GUIDE_PROMPTS = {
  idle: "Hi! I'm Eurydice. Start a session and I'll walk you through your first lesson.",
  connecting: "Setting things up — give me a moment to connect…",
  connected: "We're connected. Tell me what you'd like to work on, or I'll suggest a starting point.",
  lesson: "Follow along with the guided prompts. I'll surface controls when you need them.",
  busy: "Working on it — hang tight…",
};

function resolveGuideMessage({ isConnected, isBusy, status, runtimeSummary }) {
  if (isBusy) {
    return GUIDE_PROMPTS.busy;
  }
  if (!isConnected && status === "Connecting…") {
    return GUIDE_PROMPTS.connecting;
  }
  if (!isConnected) {
    return GUIDE_PROMPTS.idle;
  }
  if (runtimeSummary) {
    return runtimeSummary;
  }
  return GUIDE_PROMPTS.connected;
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
  orbLowPower,
  primaryActionLabel,
  onToggleMic,
  onToggleCamera,
  onInstrumentProfileChange,
  onStartTutorSession,
  onStopTutorSession,
  onPrimaryAction,
  onCapturePhrase,
  onToggleOrbLowPower,
  onToggleScoreReader,
}) {
  const [showActions, setShowActions] = useState(false);
  const guideMessage = resolveGuideMessage({ isConnected, isBusy, status, runtimeSummary });

  return (
    <aside className="glass rounded-[2.2rem] p-5">
      {/* AI guide surface — primary interaction point */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-400/15">
          <Sparkles className="h-4 w-4 text-sky-200" />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
            Gemini Live
          </div>
          <div className="mt-0.5 text-xs text-slate-400">{status}</div>
        </div>
      </div>

      <div className="mt-4 rounded-[1.8rem] border border-white/10 bg-slate-950/50 px-4 py-4">
        <div className="flex items-start gap-3">
          <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-sky-300" />
          <p className="text-sm leading-relaxed text-slate-200">{guideMessage}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={isConnected && liveMode === "GUIDED_LESSON" ? onStopTutorSession : onStartTutorSession}
        disabled={isBusy && !(isConnected && liveMode === "GUIDED_LESSON")}
        className="mt-4 flex w-full min-h-13 items-center justify-center gap-2 rounded-[1.5rem] border border-sky-300/20 bg-sky-400/12 px-4 py-3 text-sm font-semibold text-sky-50 transition hover:bg-sky-400/18 disabled:cursor-wait disabled:opacity-70"
      >
        {isConnected && liveMode === "GUIDED_LESSON" ? (
          <PauseCircle className="h-4 w-4" />
        ) : (
          <PlayCircle className="h-4 w-4" />
        )}
        {isConnected && liveMode === "GUIDED_LESSON" ? "Pause Gemini Live" : "Start Gemini Live"}
      </button>

      {/* Primary action — always visible */}
      <button
        type="button"
        onClick={onPrimaryAction}
        disabled={isBusy}
        className="mt-4 flex w-full min-h-14 items-center justify-center gap-2 rounded-[1.6rem] bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-wait disabled:opacity-70"
      >
        {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />}
        {primaryActionLabel}
      </button>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-[1.4rem] border border-white/10 bg-white/5 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Live mode
          </div>
          <div className="mt-2 text-sm font-medium text-white">{liveMode || "offline"}</div>
        </div>
        <div className="rounded-[1.4rem] border border-white/10 bg-white/5 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Audio route
          </div>
          <div className="mt-2 text-sm font-medium text-white">{liveAudioMode}</div>
        </div>
      </div>

      {/* Contextual actions — revealed on demand */}
      {isConnected && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowActions((v) => !v)}
            className="flex w-full items-center justify-between gap-2 rounded-[1.4rem] border border-white/10 bg-white/[0.04] px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300 transition hover:bg-white/[0.08]"
          >
            Actions
            <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${showActions ? "rotate-180" : ""}`} />
          </button>

          {showActions && (
            <div className="mt-3 grid gap-2">
              <button
                type="button"
                onClick={onCapturePhrase}
                disabled={isBusy}
                className="flex items-center justify-center gap-2 rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
              >
                <Mic className="h-4 w-4" />
                Capture phrase
              </button>
              <button
                type="button"
                onClick={onToggleScoreReader}
                disabled={isBusy}
                className="flex items-center justify-center gap-2 rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
              >
                <ScanLine className="h-4 w-4" />
                {isReadingScore ? "Stop reader" : "Read from camera"}
              </button>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={onToggleMic}
                  className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-3 py-2.5 text-xs font-medium transition ${
                    micEnabled ? "bg-emerald-400/15 text-emerald-100" : "bg-white/5 text-slate-400"
                  }`}
                >
                  {micEnabled ? <Mic className="h-3.5 w-3.5" /> : <MicOff className="h-3.5 w-3.5" />}
                  Mic
                </button>
                <button
                  type="button"
                  onClick={onToggleCamera}
                  className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-3 py-2.5 text-xs font-medium transition ${
                    cameraEnabled ? "bg-sky-400/15 text-sky-100" : "bg-white/5 text-slate-400"
                  }`}
                >
                  {cameraEnabled ? <Camera className="h-3.5 w-3.5" /> : <CameraOff className="h-3.5 w-3.5" />}
                  Camera
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Session tuning — collapsed by default */}
      <details className="mt-4 rounded-[1.8rem] border border-white/10 bg-slate-950/45 px-4 py-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
          <span className="inline-flex items-center gap-2">
            <SlidersHorizontal className="h-3.5 w-3.5 text-sky-300" />
            Session tuning
          </span>
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </summary>

        <div className="mt-4 space-y-4">
          <div className="rounded-[1.4rem] border border-white/10 bg-white/5 px-3 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
                  Orb performance
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  Low-power stays on by default to keep the workstation responsive.
                </div>
              </div>
              <button
                type="button"
                onClick={onToggleOrbLowPower}
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${
                  orbLowPower
                    ? "bg-amber-300/20 text-amber-100"
                    : "bg-emerald-400/15 text-emerald-100"
                }`}
              >
                <Cpu className="h-3.5 w-3.5" />
                {orbLowPower ? "Low-power" : "Adaptive"}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Instrument profile
            </label>
            <select
              value={instrumentProfile}
              onChange={(event) => onInstrumentProfileChange(event.target.value)}
              className="mt-2 w-full rounded-[1.4rem] border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
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

          <div className="rounded-[1.4rem] border border-white/10 bg-white/5 px-3 py-3 text-xs text-slate-400">
            <div className="font-semibold uppercase tracking-[0.14em] text-slate-300">Identity</div>
            <div className="mt-2 break-all">{authStatus}</div>
            {sessionId ? <div className="mt-2 text-slate-500">Session: {sessionId}</div> : null}
          </div>
        </div>
      </details>
    </aside>
  );
}
