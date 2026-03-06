import { Bot, LoaderCircle, Mic, Music4, Sparkles } from "lucide-react";

function formatInterruptType(type) {
  if (!type) {
    return "Idle";
  }
  return type.replaceAll("_", " ").toLowerCase();
}

function roleStyles(message) {
  if (message.role === "user") {
    return {
      label: "You",
      icon: Mic,
      className: "border-sky-300/20 bg-sky-400/10 text-sky-50",
    };
  }
  if (message.role === "music") {
    return {
      label: "Music",
      icon: Music4,
      className: "border-emerald-300/20 bg-emerald-400/10 text-emerald-50",
    };
  }
  if (message.role === "system") {
    return {
      label: "System",
      icon: Sparkles,
      className: "border-white/10 bg-white/5 text-slate-200",
    };
  }
  return {
    label: "Eurydice",
    icon: Bot,
    className: "border-indigo-300/20 bg-indigo-400/10 text-indigo-50",
  };
}

function SignalMeter({ label, value }) {
  const percentage = Math.max(0, Math.min(100, Math.round(Number(value || 0) * 100)));

  return (
    <div className="rounded-[1.2rem] border border-white/10 bg-slate-950/45 px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        {label}
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-white/10">
        <div
          className="h-1.5 rounded-full bg-sky-300 transition-all duration-200"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="mt-2 text-xs text-slate-300">{percentage}%</div>
    </div>
  );
}

export default function ConversationPanel({
  messages,
  liveAudioMode,
  liveAudioLevels,
  recentMusicEvents,
  interruptState,
}) {
  const assistantStreaming = messages.some(
    (message) => message.role === "assistant" && message.streaming,
  );

  return (
    <section className="glass rounded-[2rem] p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
            Live Dialogue
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">
            Gemini Live streams here while the shared audio engine keeps listening for speech and
            music interrupts.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <SignalMeter label="Speech" value={liveAudioLevels.speechConfidence} />
          <SignalMeter label="Music" value={liveAudioLevels.musicConfidence} />
          <div className="rounded-[1.2rem] border border-white/10 bg-slate-950/45 px-3 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Mode
            </div>
            <div className="mt-3 text-sm font-medium text-white">{liveAudioMode}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-[1.4rem] border border-white/10 bg-slate-950/45 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Interrupt controller
            </div>
            <div className="mt-1 text-sm text-white">
              {interruptState.status === "queued"
                ? `Queued ${formatInterruptType(interruptState.pendingType)}`
                : interruptState.status === "flushing"
                  ? `Handing ${formatInterruptType(interruptState.pendingType)} to Gemini`
                  : "Listening for speech or music"}
            </div>
          </div>
          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
            {interruptState.status}
            {interruptState.queuedCount > 1 ? ` · ${interruptState.queuedCount} queued` : ""}
          </div>
        </div>
        {interruptState.pendingSummary ? (
          <div className="mt-2 text-xs text-slate-400">{interruptState.pendingSummary}</div>
        ) : null}
      </div>

      <div className="mt-5 space-y-3">
        {messages.length ? (
          messages.slice(-10).map((message) => {
            const style = roleStyles(message);
            const IconComponent = style.icon;
            return (
              <div
                key={message.id}
                className={`rounded-[1.6rem] border px-4 py-3 ${style.className}`}
              >
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
                  <IconComponent className="h-3.5 w-3.5" />
                  {style.label}
                  {message.streaming ? (
                    <span className="inline-flex items-center gap-1 text-slate-300">
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                      Streaming
                    </span>
                  ) : null}
                </div>
                <div className="mt-2 text-sm leading-relaxed text-white">{message.text}</div>
              </div>
            );
          })
        ) : (
          <div className="rounded-[1.6rem] border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
            Gemini Live will greet you here when the workspace session connects.
          </div>
        )}

        {assistantStreaming ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
            Eurydice is streaming a response.
          </div>
        ) : null}

        {recentMusicEvents?.length ? (
          <div className="rounded-[1.4rem] border border-white/10 bg-slate-950/45 px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Recent interrupts
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {recentMusicEvents.slice(0, 3).map((event) => (
                <span
                  key={`${event.type}-${event.occurredAt}`}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200"
                >
                  {event.type === "NOTE_PLAYED"
                    ? event.pitch
                    : event.type === "PHRASE_PLAYED"
                      ? event.notes.join(" · ")
                      : `${event.tempo || "?"} BPM`}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
