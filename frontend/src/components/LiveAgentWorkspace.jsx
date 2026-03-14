import {
  Activity,
  Camera,
  CameraOff,
  LoaderCircle,
  Mic,
  MicOff,
  PlayCircle,
  Radio,
  RefreshCw,
  Send,
  Square,
  Volume2,
  Waves,
} from "lucide-react";
import MarbleSphere from "./MarbleSphere";

const MODE_OPTIONS = [
  { value: "music_tutor", label: "Music tutor" },
  { value: "sight_reading", label: "Sight reading" },
  { value: "technique_practice", label: "Technique" },
  { value: "ear_training", label: "Ear training" },
];

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

function Chip({ label, active = false, tone = "slate" }) {
  const activeTone =
    tone === "emerald"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "graphite"
        ? "border-slate-500 bg-slate-900 text-white"
        : "border-slate-300 bg-white text-slate-700";
  const idleTone = "border-slate-300 bg-white/80 text-slate-500";

  return (
    <div className={`border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${active ? activeTone : idleTone}`}>
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

function formatAssistantState(state, isConnecting, isConnected) {
  if (isConnecting) {
    return "Connecting";
  }
  if (!isConnected) {
    return "Idle";
  }
  if (state === "speaking") {
    return "Speaking";
  }
  return "Listening";
}

export default function LiveAgentWorkspace({
  profileDraft,
  setProfileDraft,
  sessionProfile,
  runtimeInfo,
  runtimeDebug,
  messages,
  summary,
  connectionError,
  conversationInput,
  setConversationInput,
  isConnecting,
  isConnected,
  assistantState,
  micEnabled,
  cameraEnabled,
  liveAudioMode,
  liveAudioLevels,
  connectionMeta,
  videoRef,
  refreshRuntime,
  startSession,
  stopSession,
  sendText,
  toggleMic,
  toggleCamera,
}) {
  const activeDebugSession = runtimeDebug?.active_sessions?.[0] || null;
  const recentSession = runtimeDebug?.recent_sessions?.[0] || null;
  const modeLabel = formatAssistantState(assistantState, isConnecting, isConnected);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.26),transparent_34%),linear-gradient(180deg,#f8f9fb_0%,#eef1f4_50%,#e7eaee_100%)] text-slate-900">
      <main className="mx-auto w-full max-w-[1680px] px-4 py-4 md:px-6 xl:px-8">
        <header className="border border-slate-300 bg-white/82 px-4 py-4 shadow-[0_18px_40px_rgba(47,52,58,0.05)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Eurydice Live
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 xl:text-4xl">
                Voice-and-camera music tutoring
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-600">
                One profile. One live session. One clean multimodal loop.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Chip label={runtimeInfo?.model_id || "Runtime"} active tone="graphite" />
              <Chip label={connectionMeta.transport || "No transport"} active={Boolean(connectionMeta.transport)} />
              <Chip label={modeLabel} active={isConnected || isConnecting} tone="emerald" />
            </div>
          </div>
        </header>

        <div className="mt-4 grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)_24rem]">
          <div className="space-y-4">
            <Panel title="Session profile" eyebrow="Input">
              <div className="grid gap-3">
                <label className="grid gap-1 text-sm">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Mode</span>
                  <select
                    value={profileDraft.mode}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, mode: event.target.value }))
                    }
                    className="border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                  >
                    {MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1 text-sm">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Instrument</span>
                  <input
                    value={profileDraft.instrument}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, instrument: event.target.value }))
                    }
                    placeholder="Voice, piano, violin"
                    className="border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                  />
                </label>

                <label className="grid gap-1 text-sm">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Piece</span>
                  <input
                    value={profileDraft.piece}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, piece: event.target.value }))
                    }
                    placeholder="Caro mio ben"
                    className="border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                  />
                </label>

                <label className="grid gap-1 text-sm">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Goal</span>
                  <textarea
                    value={profileDraft.goal}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, goal: event.target.value }))
                    }
                    placeholder="Shape the opening phrase"
                    rows={4}
                    className="border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                  />
                </label>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={toggleMic}
                  className={`flex items-center justify-center gap-2 border px-3 py-3 text-sm font-medium shadow-[6px_6px_0_rgba(184,189,197,0.24)] transition ${
                    micEnabled
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white text-slate-700"
                  }`}
                >
                  {micEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                  Mic
                </button>
                <button
                  type="button"
                  onClick={toggleCamera}
                  className={`flex items-center justify-center gap-2 border px-3 py-3 text-sm font-medium shadow-[6px_6px_0_rgba(184,189,197,0.24)] transition ${
                    cameraEnabled
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white text-slate-700"
                  }`}
                >
                  {cameraEnabled ? <Camera className="h-4 w-4" /> : <CameraOff className="h-4 w-4" />}
                  Camera
                </button>
              </div>

              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  onClick={isConnected ? stopSession : startSession}
                  className="flex min-h-13 flex-1 items-center justify-center gap-2 border border-slate-900 bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px]"
                >
                  {isConnecting ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : isConnected ? (
                    <Square className="h-4 w-4" />
                  ) : (
                    <PlayCircle className="h-4 w-4" />
                  )}
                  {isConnecting ? "Starting" : isConnected ? "Stop session" : "Start session"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void refreshRuntime();
                  }}
                  className="flex min-h-13 items-center justify-center border border-slate-300 bg-white px-4 py-3 text-slate-700 shadow-[6px_6px_0_rgba(184,189,197,0.22)]"
                  aria-label="Refresh runtime"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              {sessionProfile ? (
                <div className="mt-4 border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-700">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Normalized</div>
                  <div className="mt-2">{[sessionProfile.instrument, sessionProfile.piece, sessionProfile.goal].filter(Boolean).join(" · ") || "General music help"}</div>
                </div>
              ) : null}

              {connectionError ? (
                <div className="mt-4 border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
                  {connectionError}
                </div>
              ) : null}
            </Panel>

            <Panel title="Runtime" eyebrow="Backend">
              <div className="grid gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Model</div>
                    <div className="mt-2 text-sm font-medium text-slate-900">{runtimeInfo?.model_id || "..."}</div>
                  </div>
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Region</div>
                    <div className="mt-2 text-sm font-medium text-slate-900">{runtimeInfo?.location || "..."}</div>
                  </div>
                </div>
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Session</div>
                  <div className="mt-2 break-all text-sm font-medium text-slate-900">{connectionMeta.sessionId || "Not connected"}</div>
                </div>
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Live counts</div>
                  <div className="mt-2 text-sm text-slate-700">
                    Active {runtimeDebug?.active_session_count ?? 0}
                    {recentSession ? ` · Recent ${recentSession.transport}` : ""}
                  </div>
                </div>
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel
              title="Live surface"
              eyebrow="Studio"
              aside={<Chip label={liveAudioMode || "silence"} active={isConnected} tone="emerald" />}
            >
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem] xl:items-center">
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
                        : "Start a session to connect"}
                    </div>
                  </div>
                </div>

                <div className="grid gap-3">
                  <SignalBar label="Speech" value={liveAudioLevels.speechConfidence} />
                  <SignalBar label="Music" value={liveAudioLevels.musicConfidence} />
                  <div className="border border-slate-300 bg-white px-3 py-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Capture</div>
                    <div className="mt-2 flex items-center gap-2 text-sm font-medium text-slate-900">
                      <Waves className="h-4 w-4 text-slate-700" />
                      {liveAudioLevels.speechActive ? "Speech active" : "Waiting"}
                    </div>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel title="Camera" eyebrow="Vision">
              <div className="border border-slate-300 bg-slate-950/96">
                <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
              </div>
              <div className="mt-3 text-sm text-slate-600">
                {cameraEnabled
                  ? "Camera frames will stream while the session is live."
                  : "Enable camera if you want Eurydice to see notation or homework."}
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel title="Dialogue" eyebrow="Transcript">
              <div className="max-h-[26rem] space-y-3 overflow-auto pr-1">
                {messages.length ? (
                  messages.map((message) => <MessageCard key={message.id} message={message} />)
                ) : (
                  <div className="border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                    Start a session to see live conversation and transcripts.
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

            <Panel title="Diagnostics" eyebrow="Debug">
              <div className="grid gap-3">
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    <Activity className="h-3.5 w-3.5" />
                    Active session
                  </div>
                  <div className="mt-2 text-sm text-slate-700">
                    {activeDebugSession
                      ? `${activeDebugSession.transport} · ${activeDebugSession.mode}`
                      : "No active websocket session"}
                  </div>
                </div>
                <div className="border border-slate-300 bg-white px-3 py-3">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    <Volume2 className="h-3.5 w-3.5" />
                    Inbound
                  </div>
                  <div className="mt-2 text-sm text-slate-700">
                    {activeDebugSession?.inbound
                      ? Object.entries(activeDebugSession.inbound)
                          .map(([key, value]) => `${key} ${value}`)
                          .join(" · ")
                      : "No inbound events yet"}
                  </div>
                </div>
                {summary ? (
                  <div className="border border-slate-300 bg-[#f8f9fb] px-3 py-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      <Radio className="h-3.5 w-3.5" />
                      Summary
                    </div>
                    <div className="mt-2 space-y-1 text-sm text-slate-700">
                      {Array.isArray(summary.bullets)
                        ? summary.bullets.map((bullet) => <div key={bullet}>{bullet}</div>)
                        : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </Panel>
          </div>
        </div>
      </main>
    </div>
  );
}
