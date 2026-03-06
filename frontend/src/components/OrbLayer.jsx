import { Camera, LoaderCircle, Mic, Radio, Wifi, WifiOff } from "lucide-react";
import AudioReactiveOrb from "./AudioReactiveOrb";

function SurfaceBadge({ icon, label, active = false, tone = "sky" }) {
  const IconComponent = icon;
  const toneClass =
    tone === "emerald"
      ? active
        ? "border-emerald-300/30 bg-emerald-400/12 text-emerald-100"
        : "border-white/10 bg-white/5 text-slate-400"
      : active
        ? "border-sky-300/30 bg-sky-400/12 text-sky-100"
        : "border-white/10 bg-white/5 text-slate-400";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${toneClass}`}
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
    return "Playback focus";
  }
  if (micEnabled) {
    return "Live mic";
  }
  return "Draft mode";
}

export default function OrbLayer({
  orbProps,
  status,
  runtimeSummary,
  lessonState,
  isConnected,
  micEnabled,
  cameraEnabled,
  isReadingScore,
  isPlaying,
  isBusy,
  sessionId,
}) {
  const captureMode = resolveCaptureMode({ isReadingScore, isPlaying, micEnabled });
  const stageLabel = lessonState?.stage ? lessonState.stage.replaceAll("-", " ") : "idle";
  const prompt = lessonState?.prompt || status;

  return (
    <section className="glass relative overflow-hidden rounded-[2.4rem] px-5 py-5 md:px-7 md:py-6">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(96,165,250,0.14),transparent_38%),linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.02)_30%,rgba(2,6,23,0.18)_100%)]" />
      <div className="relative z-10 flex flex-col gap-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
              Orb Layer
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
              Central listening surface
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300">
              Keep the workspace centered on one surface. Capture, playback, and tutoring all
              resolve here before you open deeper inspectors.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <SurfaceBadge
              icon={isConnected ? Wifi : WifiOff}
              label={isConnected ? "Live linked" : "Standby"}
              active={isConnected}
            />
            <SurfaceBadge icon={Mic} label={captureMode} active={micEnabled || isPlaying} tone="emerald" />
            <SurfaceBadge icon={Camera} label={cameraEnabled ? "Camera armed" : "Camera idle"} active={cameraEnabled} />
          </div>
        </div>

        <div className="relative flex min-h-[54vh] items-center justify-center overflow-hidden rounded-[2.2rem] border border-white/10 bg-[radial-gradient(circle_at_50%_42%,rgba(56,189,248,0.12),transparent_22%),radial-gradient(circle_at_50%_62%,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(2,6,23,0.96),rgba(8,15,34,0.9)_48%,rgba(2,6,23,0.98))] px-4 py-8">
          <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(148,163,184,0.05)_1px,transparent_1px),linear-gradient(180deg,rgba(148,163,184,0.04)_1px,transparent_1px)] bg-[size:32px_32px] opacity-20" />
          <div className="absolute inset-x-[12%] top-[14%] h-40 rounded-full bg-sky-400/10 blur-3xl" />
          <div className="absolute inset-x-[18%] bottom-[10%] h-32 rounded-full bg-indigo-400/10 blur-3xl" />
          <div className="relative flex items-center justify-center">
            <div className="absolute inset-[-12%] rounded-full bg-[radial-gradient(circle_at_center,rgba(125,211,252,0.18),transparent_48%),radial-gradient(circle_at_center,rgba(99,102,241,0.14),transparent_70%)] blur-3xl" />
            <AudioReactiveOrb
              audioSource={orbProps.audioSource}
              audioElement={orbProps.audioElement}
              active={orbProps.active}
              intensity={orbProps.intensity}
              theme={orbProps.theme}
              performanceMode={orbProps.performanceMode}
              size="studio"
              className="relative z-10"
            />
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_18rem]">
          <div className="rounded-[1.6rem] border border-white/10 bg-slate-950/45 px-4 py-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {isBusy ? (
                <LoaderCircle className="h-3.5 w-3.5 animate-spin text-sky-300" />
              ) : (
                <Radio className="h-3.5 w-3.5 text-sky-300" />
              )}
              Current focus
            </div>
            <div className="mt-2 text-sm text-white">{prompt}</div>
            <div className="mt-2 text-xs text-slate-400">{runtimeSummary}</div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <div className="rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Stage
              </div>
              <div className="mt-2 text-base font-medium capitalize text-white">{stageLabel}</div>
            </div>
            <div className="rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Source
              </div>
              <div className="mt-2 text-base font-medium text-white">{captureMode}</div>
            </div>
            <div className="rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Session
              </div>
              <div className="mt-2 truncate text-base font-medium text-white">
                {sessionId || "Pending"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
