import {
  Camera,
  CameraOff,
  Cpu,
  LoaderCircle,
  Mic,
  MicOff,
  Radio,
  ScanLine,
  Settings2,
  ShieldCheck,
  Waves,
  Wifi,
  WifiOff,
} from "lucide-react";

function SessionBadge({ active, icon, label }) {
  const IconComponent = icon;
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
        active ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100" : "border-white/10 bg-white/5 text-slate-400"
      }`}
    >
      <IconComponent className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

export default function AuthPanel({
  email,
  password,
  authStatus,
  micEnabled,
  cameraEnabled,
  isConnected,
  status,
  runtimeSummary,
  sessionId,
  isReadingScore,
  instrumentProfile,
  isBusy,
  orbLowPower,
  primaryActionLabel,
  onEmailChange,
  onPasswordChange,
  onSignIn,
  onToggleMic,
  onToggleCamera,
  onInstrumentProfileChange,
  onPrimaryAction,
  onCapturePhrase,
  onToggleOrbLowPower,
  onToggleScoreReader,
}) {
  return (
    <div className="glass rounded-[2rem] p-5">
      <div className="space-y-4">
        <section className="rounded-[1.8rem] border border-white/10 bg-slate-950/45 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              <ShieldCheck className="h-4 w-4 text-sky-300" />
              Authentication
            </div>
            <div className="text-[11px] text-slate-500">{authStatus}</div>
          </div>
          <div className="mt-4 grid gap-3">
            <input
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="Email (optional)"
              className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
            />
            <input
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="Password (optional)"
              type="password"
              className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
            />
            <button
              type="button"
              onClick={onSignIn}
              className="rounded-2xl bg-sky-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
            >
              Sign In
            </button>
          </div>
        </section>

        <section className="rounded-[1.8rem] border border-white/10 bg-slate-950/45 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              <Waves className="h-4 w-4 text-sky-300" />
              Session state
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
              {isReadingScore ? "Camera reader" : "Guided lesson"}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <SessionBadge active={micEnabled} icon={Mic} label={micEnabled ? "Mic on" : "Mic off"} />
            <SessionBadge
              active={cameraEnabled}
              icon={cameraEnabled ? Camera : CameraOff}
              label={cameraEnabled ? "Camera on" : "Camera off"}
            />
            <SessionBadge
              active={isConnected}
              icon={isConnected ? Wifi : WifiOff}
              label={isConnected ? "Live linked" : "Standby"}
            />
          </div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-300">
            <div className="flex items-center gap-2 text-white">
              {isConnected ? (
                <Wifi className="h-4 w-4 text-emerald-300" />
              ) : (
                <WifiOff className="h-4 w-4 text-slate-400" />
              )}
              {status}
            </div>
            <div className="mt-2 text-xs text-slate-400">{runtimeSummary}</div>
            {sessionId ? <div className="mt-2 text-[11px] text-slate-500">Session: {sessionId}</div> : null}
          </div>
        </section>

        <section className="rounded-[1.8rem] border border-white/10 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            <Radio className="h-4 w-4 text-sky-300" />
            Capture controls
          </div>
          <div className="mt-4 grid gap-3">
            <button
              type="button"
              onClick={onPrimaryAction}
              disabled={isBusy}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-wait disabled:opacity-70"
            >
              {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Radio className="h-4 w-4" />}
              {primaryActionLabel}
            </button>
            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={onCapturePhrase}
                disabled={isBusy}
                className="flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
              >
                <Mic className="h-4 w-4" />
                Capture phrase
              </button>
              <button
                type="button"
                onClick={onToggleScoreReader}
                disabled={isBusy}
                className="flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-70"
              >
                <ScanLine className="h-4 w-4" />
                {isReadingScore ? "Stop reader" : "Read from camera"}
              </button>
            </div>
          </div>
        </section>

        <section className="rounded-[1.8rem] border border-white/10 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            <Settings2 className="h-4 w-4 text-sky-300" />
            Input & tuning
          </div>
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={onToggleMic}
                className={`flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  micEnabled ? "bg-emerald-400/15 text-emerald-200" : "bg-white/5 text-slate-400"
                }`}
              >
                {micEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                Mic {micEnabled ? "On" : "Off"}
              </button>
              <button
                type="button"
                onClick={onToggleCamera}
                className={`flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  cameraEnabled ? "bg-emerald-400/15 text-emerald-200" : "bg-white/5 text-slate-400"
                }`}
              >
                {cameraEnabled ? <Camera className="h-4 w-4" /> : <CameraOff className="h-4 w-4" />}
                Camera {cameraEnabled ? "On" : "Off"}
              </button>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
                    Orb performance
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    Low-power is the default because it keeps the workstation responsive.
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
                  {orbLowPower ? "Low-power on" : "Adaptive"}
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
                className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
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
          </div>
        </section>
      </div>
    </div>
  );
}
