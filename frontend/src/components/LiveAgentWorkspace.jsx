import {
  Camera,
  CameraOff,
  LoaderCircle,
  Mic,
  MicOff,
  RefreshCw,
  Send,
  Square,
  Volume2,
  Waves,
} from "lucide-react";
import MarbleSphere from "./MarbleSphere";

function Panel({ title, eyebrow, children, aside = null }) {
  return (
    <section className="glass border border-slate-300/90 px-4 py-4 shadow-[0_20px_42px_rgba(47,52,58,0.06)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          {eyebrow ? (
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              {eyebrow}
            </div>
          ) : null}
          <h2 className="mt-1 text-lg font-semibold text-slate-900">{title}</h2>
        </div>
        {aside}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Chip({ label, tone = "default" }) {
  const toneClass =
    tone === "dark"
      ? "border-slate-500 bg-slate-900 text-white"
      : tone === "live"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-slate-300 bg-white text-slate-700";
  return (
    <div className={`border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${toneClass}`}>
      {label}
    </div>
  );
}

function SignalBar({ label, value }) {
  const percentage = Math.max(0, Math.min(100, Math.round(Number(value || 0) * 100)));
  return (
    <div className="border border-slate-300 bg-white px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-3 h-2 bg-slate-200">
        <div className="h-2 bg-slate-900 transition-all duration-200" style={{ width: `${percentage}%` }} />
      </div>
      <div className="mt-2 text-xs text-slate-600">{percentage}%</div>
    </div>
  );
}

function MessageCard({ message }) {
  const roleLabel =
    message.role === "assistant" ? "Eurydice" : message.role === "user" ? "You" : "System";
  const toneClass =
    message.role === "assistant"
      ? "border-slate-500 bg-slate-900 text-white"
      : message.role === "user"
        ? "border-slate-300 bg-white text-slate-800"
        : "border-slate-300 bg-[#f8f9fb] text-slate-700";

  return (
    <article className={`border px-4 py-3 ${toneClass}`}>
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
        {roleLabel}
        {message.partial ? (
          <span className="inline-flex items-center gap-1 text-current/70">
            <LoaderCircle className="h-3 w-3 animate-spin" />
            Live
          </span>
        ) : null}
      </div>
      <div className="mt-2 text-sm leading-relaxed">{message.text}</div>
    </article>
  );
}

function ToggleButton({ active, onClick, ActiveIcon, IdleIcon, activeLabel, idleLabel }) {
  const Icon = active ? ActiveIcon : IdleIcon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-12 items-center justify-center gap-2 border px-3 py-3 text-sm font-medium shadow-[6px_6px_0_rgba(184,189,197,0.24)] transition ${
        active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700"
      }`}
    >
      <Icon className="h-4 w-4" />
      {active ? activeLabel : idleLabel}
    </button>
  );
}

function formatAssistantState(state, isConnected) {
  if (!isConnected) {
    return "Closing";
  }
  if (state === "speaking") {
    return "Speaking";
  }
  return "Listening";
}

function formatMode(mode) {
  return typeof mode === "string" ? mode.replaceAll("_", " ") : "General";
}

export default function LiveAgentWorkspace({
  sessionProfile,
  runtimeInfo,
  runtimeDebug,
  messages,
  summary,
  connectionError,
  conversationInput,
  setConversationInput,
  isConnected,
  assistantState,
  micEnabled,
  cameraEnabled,
  liveAudioMode,
  liveAudioLevels,
  connectionMeta,
  videoRef,
  refreshRuntime,
  stopSession,
  sendText,
  toggleMic,
  toggleCamera,
}) {
  const activeDebugSession = runtimeDebug?.active_sessions?.[0] || null;
  const modeLabel = formatAssistantState(assistantState, isConnected);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.26),transparent_32%),linear-gradient(180deg,#f8f9fb_0%,#eef1f4_50%,#e7eaee_100%)] text-slate-900">
      <main className="mx-auto w-full max-w-[1460px] px-4 py-4 md:px-6 xl:px-8">
        <header className="glass border border-slate-300/90 px-4 py-4 shadow-[0_20px_42px_rgba(47,52,58,0.06)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="inline-flex items-center gap-3 border border-slate-300 bg-white px-4 py-3 shadow-[0_10px_22px_rgba(47,52,58,0.04)]">
                <img src="/logo.svg" alt="Eurydice" className="h-4 w-auto" />
              </div>
              <div className="mt-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Live workspace
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 xl:text-4xl">
                {sessionProfile?.piece || "Live coaching"}{sessionProfile?.instrument ? ` · ${sessionProfile.instrument}` : ""}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {sessionProfile?.goal || "Talk, show, and adjust in one session."}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Chip label={runtimeInfo?.model_id || "Runtime"} tone="dark" />
              <Chip label={connectionMeta.transport || "No transport"} />
              <Chip label={modeLabel} tone="live" />
              <button
                type="button"
                onClick={stopSession}
                className="inline-flex min-h-12 items-center gap-2 border border-slate-900 bg-slate-900 px-4 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px]"
              >
                <Square className="h-4 w-4" />
                End
              </button>
            </div>
          </div>
        </header>

        <div className="mt-4 grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_22rem]">
          <div className="space-y-4">
            <Panel title="Session" eyebrow="Profile">
              <div className="grid gap-3">
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Mode</div>
                  <div className="mt-2 text-sm font-medium text-slate-900">{formatMode(sessionProfile?.mode)}</div>
                </div>
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Piece</div>
                  <div className="mt-2 text-sm font-medium text-slate-900">{sessionProfile?.piece || "General practice"}</div>
                </div>
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Goal</div>
                  <div className="mt-2 text-sm text-slate-700">{sessionProfile?.goal || "Listen and guide."}</div>
                </div>
              </div>
            </Panel>

            <Panel title="Controls" eyebrow="Input">
              <div className="grid gap-2">
                <ToggleButton
                  active={micEnabled}
                  onClick={toggleMic}
                  ActiveIcon={Mic}
                  IdleIcon={MicOff}
                  activeLabel="Mic on"
                  idleLabel="Mic off"
                />
                <ToggleButton
                  active={cameraEnabled}
                  onClick={toggleCamera}
                  ActiveIcon={Camera}
                  IdleIcon={CameraOff}
                  activeLabel="Camera on"
                  idleLabel="Camera off"
                />
                <button
                  type="button"
                  onClick={() => {
                    void refreshRuntime();
                  }}
                  className="flex min-h-12 items-center justify-center gap-2 border border-slate-300 bg-white px-3 py-3 text-sm font-medium text-slate-700 shadow-[6px_6px_0_rgba(184,189,197,0.24)]"
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </button>
              </div>

              {connectionError ? (
                <div className="mt-3 border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
                  {connectionError}
                </div>
              ) : null}
            </Panel>

            <Panel title="Signals" eyebrow="Audio">
              <div className="grid gap-3">
                <SignalBar label="Speech" value={liveAudioLevels.speechConfidence} />
                <SignalBar label="Music" value={liveAudioLevels.musicConfidence} />
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Capture</div>
                  <div className="mt-2 flex items-center gap-2 text-sm font-medium text-slate-900">
                    <Waves className="h-4 w-4 text-slate-700" />
                    {liveAudioLevels.speechActive ? "Speech active" : liveAudioMode || "Silence"}
                  </div>
                </div>
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel title="Live surface" eyebrow="Studio" aside={<Chip label={modeLabel} tone="live" />}>
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_16rem] xl:items-center">
                <div className="flex flex-col items-center justify-center">
                  <MarbleSphere className="mx-auto max-w-[30rem]" />
                  <div className="mt-5 text-center">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Assistant
                    </div>
                    <div className="mt-2 text-2xl font-semibold text-slate-950">{modeLabel}</div>
                    <div className="mt-1 text-sm text-slate-600">
                      {connectionMeta.transport
                        ? `${connectionMeta.transport} · ${connectionMeta.location || "live"}`
                        : "Waiting for transport"}
                    </div>
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Session id
                    </div>
                    <div className="mt-2 break-all text-sm text-slate-700">
                      {connectionMeta.sessionId || "Pending"}
                    </div>
                  </div>
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Region
                    </div>
                    <div className="mt-2 text-sm text-slate-700">{runtimeInfo?.location || "..."}</div>
                  </div>
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Active
                    </div>
                    <div className="mt-2 text-sm text-slate-700">
                      {runtimeDebug?.active_session_count ?? 0} live session
                      {(runtimeDebug?.active_session_count ?? 0) === 1 ? "" : "s"}
                    </div>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel title="Dialogue" eyebrow="Transcript">
              <div className="max-h-[30rem] space-y-3 overflow-auto pr-1">
                {messages.length ? (
                  messages.map((message) => <MessageCard key={message.id} message={message} />)
                ) : (
                  <div className="border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                    Waiting for the first turn.
                  </div>
                )}
              </div>

              <div className="mt-4 flex gap-2">
                <input
                  value={conversationInput}
                  onChange={(event) => setConversationInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      sendText();
                    }
                  }}
                  placeholder="Type a follow-up"
                  className="min-h-13 flex-1 border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                />
                <button
                  type="button"
                  onClick={sendText}
                  disabled={!isConnected}
                  className="flex min-h-13 items-center justify-center border border-slate-900 bg-slate-900 px-4 text-white shadow-[6px_6px_0_rgba(47,52,58,0.14)] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel title="Camera" eyebrow="Vision">
              <div className="border border-slate-300 bg-slate-950/96">
                <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
              </div>
              <div className="mt-3 text-sm text-slate-600">
                {cameraEnabled
                  ? "Frames stream while the session is live."
                  : "Enable camera if you want Eurydice to see notation or homework."}
              </div>
            </Panel>

            <Panel title="Notes" eyebrow="Summary">
              {summary?.bullets?.length ? (
                <div className="space-y-2">
                  {summary.bullets.map((bullet) => (
                    <div key={bullet} className="border border-slate-300 bg-white px-3 py-3 text-sm text-slate-700">
                      {bullet}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  Summary will land here when the session closes.
                </div>
              )}
            </Panel>

            <Panel title="Inbound" eyebrow="Debug">
              <div className="border border-slate-300 bg-white px-3 py-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  <Volume2 className="h-3.5 w-3.5" />
                  Events
                </div>
                <div className="mt-2 text-sm text-slate-700">
                  {activeDebugSession?.inbound
                    ? Object.entries(activeDebugSession.inbound)
                        .map(([key, value]) => `${key} ${value}`)
                        .join(" · ")
                    : "No inbound events yet"}
                </div>
              </div>
            </Panel>
          </div>
        </div>
      </main>
    </div>
  );
}
