import { Camera, LoaderCircle, Mic, Radio, Wifi, WifiOff } from "lucide-react";
import MarbleSphere from "./MarbleSphere";

function SurfaceBadge({ icon, label, active = false, tone = "graphite" }) {
  const IconComponent = icon;
  const toneClass =
    tone === "emerald"
      ? active
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-slate-300 bg-white/70 text-slate-500"
      : active
        ? "border-slate-400 bg-slate-900 text-white"
        : "border-slate-300 bg-white/70 text-slate-500";

  return (
    <div
      className={`inline-flex items-center gap-2 border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${toneClass}`}
    >
      <IconComponent className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

function resolveCaptureMode({ isReadingScore, isPlaying, micEnabled }) {
  if (isReadingScore) {
    return "Camera reader";
  }
  if (isPlaying) {
    return "Playback";
  }
  if (micEnabled) {
    return "Microphone";
  }
  return "Manual";
}

export default function OrbLayer({
  status,
  runtimeSummary,
  lessonState,
  lessonFlow,
  isConnected,
  micEnabled,
  cameraEnabled,
  isReadingScore,
  isPlaying,
  isBusy,
  isSessionStarting,
  sessionId,
  liveAudioMode,
  interruptState,
}) {
  const captureMode = resolveCaptureMode({ isReadingScore, isPlaying, micEnabled });
  const phaseLabel = lessonFlow?.phase || lessonState?.stage || "idle";
  const stageLabel = phaseLabel.replaceAll("-", " ").replaceAll("_", " ");
  const prompt = lessonFlow?.status || lessonState?.prompt || status;
  const sessionLabel = isSessionStarting ? "Starting" : isConnected ? "Live" : "Closed";

  return (
    <section className="glass border border-slate-300/90 px-4 py-4 shadow-[0_22px_44px_rgba(47,52,58,0.06)] md:px-6 md:py-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Orb
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900 md:text-3xl">Central studio</h2>
          <p className="mt-1 max-w-xl text-sm text-slate-600">One object. One lesson loop.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <SurfaceBadge
            icon={isConnected ? Wifi : WifiOff}
            label={sessionLabel}
            active={isConnected || isSessionStarting}
          />
          <SurfaceBadge
            icon={Mic}
            label={captureMode}
            active={micEnabled || isPlaying}
            tone="emerald"
          />
          <SurfaceBadge
            icon={Camera}
            label={cameraEnabled ? "Camera armed" : "Camera idle"}
            active={cameraEnabled}
          />
        </div>
      </div>

      <div className="mt-4 border border-slate-300/90 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.98),rgba(242,243,245,0.98)_48%,rgba(230,232,235,1)_100%)] px-4 py-5 md:px-5 md:py-6">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_21rem] xl:items-center">
          <div className="flex flex-col items-center justify-center">
            <MarbleSphere className="mx-auto" />
            <div className="mt-5 max-w-xl text-center">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Focus
              </div>
              <div className="mt-2 text-base font-medium text-slate-900">{prompt}</div>
              <div className="mt-1 text-sm text-slate-600">{runtimeSummary}</div>
            </div>
          </div>

          <div className="grid gap-3">
            <div className="border border-slate-300 bg-white/80 px-4 py-4 shadow-[0_14px_30px_rgba(47,52,58,0.05)]">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {isBusy || isSessionStarting ? (
                  <LoaderCircle className="h-3.5 w-3.5 animate-spin text-slate-700" />
                ) : (
                  <Radio className="h-3.5 w-3.5 text-slate-700" />
                )}
                Session status
              </div>
              <div className="mt-2 text-lg font-medium capitalize text-slate-900">{stageLabel}</div>
              <div className="mt-1 text-sm text-slate-600">
                {isSessionStarting
                  ? "Opening live tutor."
                  : isConnected
                    ? "Tutor active."
                    : "Tutor closed."}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div className="border border-slate-300 bg-white/80 px-4 py-3 shadow-[0_14px_30px_rgba(47,52,58,0.05)]">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Audio
                </div>
                <div className="mt-2 text-base font-medium text-slate-900">
                  {liveAudioMode && liveAudioMode !== "SILENCE" ? liveAudioMode : captureMode}
                </div>
              </div>
              <div className="border border-slate-300 bg-white/80 px-4 py-3 shadow-[0_14px_30px_rgba(47,52,58,0.05)]">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Interrupts
                </div>
                <div className="mt-2 text-base font-medium capitalize text-slate-900">
                  {interruptState?.status || "idle"}
                </div>
                {interruptState?.pendingSummary ? (
                  <div className="mt-1 text-xs text-slate-500">{interruptState.pendingSummary}</div>
                ) : null}
              </div>
              <div className="border border-slate-300 bg-white/80 px-4 py-3 shadow-[0_14px_30px_rgba(47,52,58,0.05)]">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Session
                </div>
                <div className="mt-2 truncate text-base font-medium text-slate-900">
                  {sessionId || "Not started"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
