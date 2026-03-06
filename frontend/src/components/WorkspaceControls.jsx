import {
  Camera,
  CameraOff,
  ChevronDown,
  Cpu,
  LoaderCircle,
  Mic,
  MicOff,
  Radio,
  ScanLine,
  SlidersHorizontal,
  Wifi,
  WifiOff,
} from "lucide-react";

function SessionChip({ icon, label, active = false, tone = "sky" }) {
  const IconComponent = icon;
  const toneClass =
    tone === "emerald"
      ? active
        ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
        : "border-white/10 bg-white/5 text-slate-400"
      : active
        ? "border-sky-300/30 bg-sky-400/10 text-sky-100"
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

export default function WorkspaceControls({
  authStatus,
  micEnabled,
  cameraEnabled,
  instrumentProfile,
  isConnected,
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
  onPrimaryAction,
  onCapturePhrase,
  onToggleOrbLowPower,
  onToggleScoreReader,
}) {
  return (
    <aside className="glass rounded-[2.2rem] p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
            Primary Control
          </div>
          <h2 className="mt-2 text-xl font-semibold text-white">Session deck</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
          {isReadingScore ? "Camera" : "Lesson"}
        </div>
      </div>

      <div className="mt-4 rounded-[1.8rem] border border-white/10 bg-slate-950/50 px-4 py-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          Live state
        </div>
        <div className="mt-2 text-sm text-white">{status}</div>
        <div className="mt-2 text-xs text-slate-400">{runtimeSummary}</div>
        <div className="mt-3 flex flex-wrap gap-2">
          <SessionChip icon={micEnabled ? Mic : MicOff} label={micEnabled ? "Mic on" : "Mic off"} active={micEnabled} tone="emerald" />
          <SessionChip
            icon={cameraEnabled ? Camera : CameraOff}
            label={cameraEnabled ? "Camera on" : "Camera off"}
            active={cameraEnabled}
          />
          <SessionChip
            icon={isConnected ? Wifi : WifiOff}
            label={isConnected ? "Linked" : "Standby"}
            active={isConnected}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3">
        <button
          type="button"
          onClick={onPrimaryAction}
          disabled={isBusy}
          className="flex min-h-14 items-center justify-center gap-2 rounded-[1.6rem] bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-wait disabled:opacity-70"
        >
          {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />}
          {primaryActionLabel}
        </button>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          <button
            type="button"
            onClick={onCapturePhrase}
            disabled={isBusy}
            className="flex min-h-13 items-center justify-center gap-2 rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
          >
            <Mic className="h-4 w-4" />
            Capture phrase
          </button>
          <button
            type="button"
            onClick={onToggleScoreReader}
            disabled={isBusy}
            className="flex min-h-13 items-center justify-center gap-2 rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
          >
            <ScanLine className="h-4 w-4" />
            {isReadingScore ? "Stop reader" : "Read from camera"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
        <button
          type="button"
          onClick={onToggleMic}
          className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition ${
            micEnabled ? "bg-emerald-400/15 text-emerald-100" : "bg-white/5 text-slate-400"
          }`}
        >
          {micEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
          Mic {micEnabled ? "On" : "Off"}
        </button>
        <button
          type="button"
          onClick={onToggleCamera}
          className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition ${
            cameraEnabled ? "bg-sky-400/15 text-sky-100" : "bg-white/5 text-slate-400"
          }`}
        >
          {cameraEnabled ? <Camera className="h-4 w-4" /> : <CameraOff className="h-4 w-4" />}
          Camera {cameraEnabled ? "On" : "Off"}
        </button>
      </div>

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
