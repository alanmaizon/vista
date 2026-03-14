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
      className: "border-slate-300 bg-white text-slate-800",
    };
  }
  if (message.role === "music") {
    return {
      label: "Music",
      icon: Music4,
      className: "border-emerald-200 bg-emerald-50 text-emerald-800",
    };
  }
  if (message.role === "system") {
    return {
      label: "System",
      icon: Sparkles,
      className: "border-slate-300 bg-[#f8f9fb] text-slate-700",
    };
  }
  return {
    label: "Eurydice",
    icon: Bot,
    className: "border-slate-400 bg-slate-900 text-white",
  };
}

function SignalMeter({ label, value }) {
  const percentage = Math.max(0, Math.min(100, Math.round(Number(value || 0) * 100)));

  return (
    <div className="border border-slate-300 bg-white px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        {label}
      </div>
      <div className="mt-2 h-1.5 bg-slate-200">
        <div
          className="h-1.5 bg-slate-700 transition-all duration-200"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="mt-2 text-xs text-slate-600">{percentage}%</div>
    </div>
  );
}

export default function ConversationPanel({
  messages,
  lessonFlow,
  liveAudioMode,
  liveAudioLevels,
  recentMusicEvents,
  interruptState,
}) {
  const assistantStreaming = messages.some(
    (message) => message.role === "assistant" && message.streaming,
  );

  return (
    <section className="glass border border-slate-300/90 p-4 shadow-[0_18px_38px_rgba(47,52,58,0.05)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Dialogue
          </div>
          <p className="mt-1 text-sm text-slate-600">Speech, music, interrupts.</p>
          {lessonFlow?.phase ? (
            <div className="mt-2 text-xs text-slate-500">
              Lesson phase: <span className="font-medium text-slate-700">{lessonFlow.phase}</span>
            </div>
          ) : null}
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <SignalMeter label="Speech" value={liveAudioLevels.speechConfidence} />
          <SignalMeter label="Music" value={liveAudioLevels.musicConfidence} />
          <div className="border border-slate-300 bg-white px-3 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Mode
            </div>
            <div className="mt-3 text-sm font-medium text-slate-900">{liveAudioMode}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 border border-slate-300 bg-[#f8f9fb] px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Interrupts
            </div>
            <div className="mt-1 text-sm text-slate-900">
              {interruptState.status === "queued"
                ? `Queued ${formatInterruptType(interruptState.pendingType)}`
                : interruptState.status === "flushing"
                  ? `Sending ${formatInterruptType(interruptState.pendingType)}`
                  : "Listening"}
            </div>
          </div>
          <div className="border border-slate-300 bg-white px-3 py-1 text-xs text-slate-600">
            {interruptState.status}
            {interruptState.queuedCount > 1 ? ` · ${interruptState.queuedCount} queued` : ""}
          </div>
        </div>
        {interruptState.pendingSummary ? (
          <div className="mt-2 text-xs text-slate-500">{interruptState.pendingSummary}</div>
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
                className={`border px-4 py-3 ${style.className}`}
              >
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
                  <IconComponent className="h-3.5 w-3.5" />
                  {style.label}
                  {message.streaming ? (
                    <span className="inline-flex items-center gap-1 text-slate-500">
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                      Streaming
                    </span>
                  ) : null}
                </div>
                <div className="mt-2 text-sm leading-relaxed">{message.text}</div>
              </div>
            );
          })
        ) : (
          <div className="border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
            Start Session to open Gemini Live.
          </div>
        )}

        {assistantStreaming ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
            Eurydice is streaming a response.
          </div>
        ) : null}

        {recentMusicEvents?.length ? (
          <div className="border border-slate-300 bg-white px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Recent interrupts
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {recentMusicEvents.slice(0, 3).map((event) => (
                <span
                  key={`${event.type}-${event.occurredAt}`}
                  className="border border-slate-300 bg-[#f8f9fb] px-3 py-1 text-xs text-slate-700"
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
