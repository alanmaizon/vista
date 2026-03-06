import { useMemo, useState } from "react";
import {
  Camera,
  ChevronRight,
  FileMusic,
  Mic,
  Music2,
  Play,
  ScanLine,
  Sparkles,
  Waves,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

const WORKFLOW_STEPS = [
  { key: "draft", label: "Draft" },
  { key: "prepare", label: "Prepare" },
  { key: "perform", label: "Perform" },
  { key: "compare", label: "Compare" },
  { key: "review", label: "Review" },
];

function noteClass({ active, mismatch }) {
  if (mismatch === "pitch") {
    return "border-red-300 bg-red-50 text-red-900";
  }
  if (mismatch === "rhythm") {
    return "border-amber-300 bg-amber-50 text-amber-900";
  }
  if (active) {
    return "border-sky-300 bg-sky-50 text-sky-900";
  }
  return "border-slate-200 bg-white text-slate-700";
}

function workflowStepIndex({ activeScore, lessonState, isBusy }) {
  if (!activeScore) {
    return 0;
  }
  if (isBusy && lessonState.stage === "idle") {
    return 1;
  }
  if (lessonState.stage === "awaiting-compare") {
    return 2;
  }
  if (lessonState.stage === "reviewed") {
    return 3;
  }
  if (lessonState.stage === "complete") {
    return 4;
  }
  return 1;
}

function SignalBars({ active }) {
  return (
    <div className="signal-bars" aria-hidden="true">
      {Array.from({ length: 18 }).map((_, index) => (
        <span
          key={index}
          className={`signal-bar ${active ? "signal-bar-active" : "signal-bar-idle"}`}
          style={{
            "--signal-delay": `${index * 72}ms`,
            "--signal-height": `${30 + (index % 6) * 9}%`,
          }}
        />
      ))}
    </div>
  );
}

function WorkflowRail({ activeScore, lessonState, isBusy }) {
  const currentStep = workflowStepIndex({ activeScore, lessonState, isBusy });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        <span>Capture timeline</span>
        <span>{WORKFLOW_STEPS[currentStep]?.label}</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-5 xl:grid-cols-1 2xl:grid-cols-5">
        {WORKFLOW_STEPS.map((step, index) => {
          const isCurrent = index === currentStep;
          const isComplete = index < currentStep;
          return (
            <div
              key={step.key}
              className={`rounded-2xl border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                isCurrent
                  ? "border-sky-300/40 bg-sky-400/15 text-sky-100"
                  : isComplete
                    ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
                    : "border-white/10 bg-white/5 text-slate-400"
              }`}
            >
              {step.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatusChip({ icon, label, active, tone = "sky" }) {
  const IconComponent = icon;
  const toneClasses =
    tone === "emerald"
      ? active
        ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
        : "border-white/10 bg-white/5 text-slate-400"
      : active
        ? "border-sky-300/30 bg-sky-400/10 text-sky-100"
        : "border-white/10 bg-white/5 text-slate-400";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${toneClasses}`}>
      <IconComponent className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

export function ComposerPanel({
  scoreLine,
  onScoreLineChange,
  activeScore,
  lessonState,
  detectedTempo,
}) {
  const noteCount = activeScore?.expected_notes?.length ?? 0;
  const measureCount = activeScore?.measures?.length ?? 0;

  return (
    <div className="glass rounded-3xl p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            <FileMusic className="h-4 w-4 text-sky-300" />
            Composition draft
          </div>
          <p className="mt-2 max-w-2xl text-sm text-slate-300">
            Keep the current phrase or bar editable here. This is the source Eurydice prepares before capture and comparison.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
            <div className="text-slate-500">Bars</div>
            <div className="mt-1 text-sm text-white">{measureCount || "—"}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
            <div className="text-slate-500">Notes</div>
            <div className="mt-1 text-sm text-white">{noteCount || "—"}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
            <div className="text-slate-500">Tempo</div>
            <div className="mt-1 text-sm text-white">{detectedTempo ? Math.round(detectedTempo) : "—"}</div>
          </div>
        </div>
      </div>
      <textarea
        value={scoreLine}
        onChange={(event) => onScoreLineChange(event.target.value)}
        rows={4}
        className="mt-4 w-full rounded-3xl border border-white/10 bg-slate-950/60 px-4 py-4 text-sm text-slate-100 outline-none transition focus:border-sky-300/60"
        placeholder="C4/q D4/q E4/h | G4/q A4/q B4/h"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em]">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-400">
          Guided lesson source
        </span>
        {lessonState.measureIndex != null ? (
          <span className="rounded-full border border-sky-300/25 bg-sky-400/10 px-3 py-1 text-sky-100">
            Active bar {lessonState.measureIndex}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function LiveFeedPanel({
  videoRef,
  isReadingScore,
  status,
  isConnected,
  isBusy,
  micEnabled,
  cameraEnabled,
  isPlaying,
  sessionId,
  lessonState,
  activeScore,
}) {
  const signalActive = isPlaying || isReadingScore || (micEnabled && (isConnected || isBusy));
  const captureMode = isReadingScore ? "Camera reader" : isPlaying ? "Playback analysis" : "Mic monitoring";

  return (
    <div className="glass rounded-3xl p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            <Waves className="h-4 w-4 text-sky-300" />
            Live feed
          </div>
          <p className="mt-2 text-sm text-slate-300">
            Live capture stays in the center of the lesson loop. Record, compare, or scan a bar without leaving the workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusChip icon={Mic} label={micEnabled ? "Mic ready" : "Mic off"} active={micEnabled} tone="emerald" />
          <StatusChip
            icon={Camera}
            label={cameraEnabled ? "Camera ready" : "Camera off"}
            active={cameraEnabled}
          />
          <StatusChip
            icon={ScanLine}
            label={isReadingScore ? "Reading bar" : captureMode}
            active={isReadingScore || isPlaying}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-4 2xl:grid-cols-[minmax(0,1.15fr)_22rem]">
        <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/75">
          {cameraEnabled || isReadingScore ? (
            <video ref={videoRef} autoPlay muted playsInline className="aspect-[16/10] w-full object-cover" />
          ) : (
            <div className="relative flex aspect-[16/10] items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_50%_35%,rgba(56,189,248,0.18),transparent_26%),linear-gradient(180deg,rgba(8,15,34,0.92),rgba(3,7,18,1))]">
              <div className="absolute inset-x-8 bottom-8 top-8 rounded-[1.8rem] border border-white/8 bg-[linear-gradient(180deg,rgba(56,189,248,0.08),rgba(15,23,42,0.0))]" />
              <div className="relative z-10 flex w-full max-w-[32rem] flex-col items-center px-8">
                <SignalBars active={signalActive} />
                <div className="mt-6 flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-200">
                  <span className={`status-dot ${signalActive ? "status-dot-live" : ""}`} />
                  {captureMode}
                </div>
                <div className="mt-3 max-w-sm text-center text-sm text-slate-300">
                  {cameraEnabled
                    ? "Camera is armed. Start the reader to scan a bar."
                    : "Mic and playback activity will animate this signal deck during capture and listening."}
                </div>
              </div>
            </div>
          )}
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between border-t border-white/10 bg-slate-950/70 px-4 py-3 text-xs text-slate-300 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <span className={`status-dot ${isBusy || isReadingScore ? "status-dot-live" : ""}`} />
              {status}
            </div>
            {sessionId ? <div className="truncate text-slate-500">Session {sessionId}</div> : null}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-[1.8rem] border border-white/10 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              <span>Signal preview</span>
              <span>{signalActive ? "Active" : "Idle"}</span>
            </div>
            <div className="mt-4 rounded-[1.4rem] border border-white/8 bg-white/5 px-4 py-5">
              <SignalBars active={signalActive} />
            </div>
          </div>

          <div className="rounded-[1.8rem] border border-white/10 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              <span>Session context</span>
              <span>{isConnected ? "Linked" : "Standby"}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-200">
              <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">State</div>
                <div className="mt-1 font-medium text-white">{lessonState.stage}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Source</div>
                <div className="mt-1 font-medium text-white">
                  {isReadingScore ? "Camera" : isPlaying ? "Playback" : micEnabled ? "Mic" : "Manual"}
                </div>
              </div>
            </div>
            <div className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-300">
              {activeScore
                ? "Prepared score is loaded. Capture and compare without leaving the current lesson surface."
                : "No prepared score yet. Draft a phrase and run Prepare lesson to populate the loop."}
            </div>
          </div>

          <div className="rounded-[1.8rem] border border-white/10 bg-slate-950/50 p-4">
            <WorkflowRail activeScore={activeScore} lessonState={lessonState} isBusy={isBusy} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function RenderedScorePanel({
  activeScore,
  activeNoteRange,
  comparisonStateByIndex,
  lessonState,
  isPlaying,
  detectedTempo,
  tempoOverride,
  onTempoOverrideChange,
  onPlayScore,
  onPlayAnalysis,
  hasAnalysisPlayback,
}) {
  const [zoomPercent, setZoomPercent] = useState(100);

  const zoomScale = useMemo(() => zoomPercent / 100, [zoomPercent]);
  const contentWidth = useMemo(() => `${100 / zoomScale}%`, [zoomScale]);

  const adjustZoom = (delta) => {
    setZoomPercent((current) => Math.max(70, Math.min(165, current + delta)));
  };

  return (
    <div className="glass rounded-[2rem] p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            <Music2 className="h-4 w-4 text-sky-300" />
            Rendered score
          </div>
          <p className="mt-2 text-sm text-slate-300">
            The score canvas is the main composition surface. Playback, zoom, and note-state feedback stay attached to the notation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {lessonState.measureIndex != null ? (
            <span className="rounded-full border border-sky-300/25 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-100">
              Bar {lessonState.measureIndex}
            </span>
          ) : null}
          {detectedTempo ? (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
              Phrase {Math.round(detectedTempo)} BPM
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onPlayScore}
            disabled={isPlaying || !activeScore?.measures?.length}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {isPlaying ? "Playing..." : "Play score"}
          </button>
          <button
            type="button"
            onClick={onPlayAnalysis}
            disabled={isPlaying || !hasAnalysisPlayback}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            Play phrase
          </button>
          <input
            value={tempoOverride}
            onChange={(event) => onTempoOverrideChange(event.target.value)}
            inputMode="numeric"
            placeholder="Tempo"
            className="w-24 rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-300/60"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => adjustZoom(-10)}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 transition hover:bg-white/10"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-100">
            {zoomPercent}%
          </div>
          <button
            type="button"
            onClick={() => adjustZoom(10)}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 transition hover:bg-white/10"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setZoomPercent(100)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10"
          >
            Fit
          </button>
        </div>
      </div>

      <div className="mt-5 overflow-auto rounded-[2rem] border border-slate-200 bg-white p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
        {activeScore?.svg ? (
          <div
            style={{
              width: contentWidth,
              transform: `scale(${zoomScale})`,
              transformOrigin: "top left",
            }}
          >
            <div dangerouslySetInnerHTML={{ __html: activeScore.svg }} />
          </div>
        ) : activeScore?.musicxml ? (
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">{activeScore.musicxml}</pre>
        ) : (
          <div className="flex min-h-[16rem] items-center justify-center text-sm text-slate-500">
            Prepare a lesson to render notation here.
          </div>
        )}
      </div>

      {activeScore?.expected_notes?.length ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            <ChevronRight className="h-4 w-4 text-sky-300" />
            Note-state timeline
          </div>
          <div className="flex flex-wrap gap-2">
            {activeScore.expected_notes.map((note, index) => {
              const active = activeNoteRange && index >= activeNoteRange.start && index < activeNoteRange.end;
              const mismatch = comparisonStateByIndex.get(index);
              return (
                <span
                  key={`${note.note_name}-${index}`}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${noteClass({
                    active,
                    mismatch,
                  })}`}
                >
                  {note.note_name}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ScoreWorkspace(props) {
  return (
    <>
      <ComposerPanel {...props} />
      <LiveFeedPanel {...props} />
      <RenderedScorePanel {...props} />
    </>
  );
}
