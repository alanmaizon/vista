import {
  Camera,
  CameraOff,
  LoaderCircle,
  Mic,
  MicOff,
  Radio,
  ScanLine,
  Wifi,
  WifiOff,
} from "lucide-react";

export default function AuthPanel({
  firebaseConfigText,
  email,
  password,
  authStatus,
  micEnabled,
  cameraEnabled,
  isConnected,
  status,
  runtimeSummary,
  sessionId,
  skill,
  isBusy,
  primaryActionLabel,
  onFirebaseConfigChange,
  onEmailChange,
  onPasswordChange,
  onSignIn,
  onToggleMic,
  onToggleCamera,
  onPrimaryAction,
}) {
  return (
    <div className="glass rounded-3xl p-5">
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              Firebase config
            </label>
            <div className="text-[11px] text-slate-400">{authStatus}</div>
          </div>
          <textarea
            value={firebaseConfigText}
            onChange={(event) => onFirebaseConfigChange(event.target.value)}
            rows={5}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-3 text-xs text-slate-200 outline-none focus:border-sky-300/60"
          />
          <div className="grid gap-3 md:grid-cols-2">
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
          </div>
          <button
            type="button"
            onClick={onSignIn}
            className="rounded-2xl bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
          >
            Sign In
          </button>
        </div>

        <div className="space-y-4 rounded-3xl border border-white/10 bg-slate-950/40 p-4">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              Session
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
              {skill === "READ_SCORE" ? "Vision + notation" : "Audio-first"}
            </div>
          </div>
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
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-300">
            <div className="flex items-center gap-2 text-white">
              {isConnected ? (
                <Wifi className="h-4 w-4 text-emerald-300" />
              ) : (
                <WifiOff className="h-4 w-4 text-slate-400" />
              )}
              {status}
            </div>
            <div className="mt-2 text-xs text-slate-400">{runtimeSummary}</div>
            {sessionId ? (
              <div className="mt-2 text-[11px] text-slate-500">Session: {sessionId}</div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onPrimaryAction}
            disabled={isBusy}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-wait disabled:opacity-70"
          >
            {isBusy ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : skill === "READ_SCORE" ? (
              <ScanLine className="h-4 w-4" />
            ) : (
              <Radio className="h-4 w-4" />
            )}
            {primaryActionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
