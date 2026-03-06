const FEEDBACK_METRICS = [
  { key: "pitchAccuracy", label: "Pitch accuracy" },
  { key: "rhythmAccuracy", label: "Rhythm accuracy" },
  { key: "tempoStability", label: "Tempo stability" },
  { key: "dynamicRange", label: "Dynamic range" },
  { key: "articulationVariance", label: "Articulation variance" },
];

function normalizeMetricValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(1, numeric));
}

function FeedbackMeters({ title, feedback }) {
  if (!feedback || typeof feedback !== "object") {
    return null;
  }
  return (
    <div className="mt-3 rounded-2xl border border-white/10 bg-slate-950/45 px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-300">{title}</div>
      <div className="mt-3 space-y-2">
        {FEEDBACK_METRICS.map((metric) => {
          const value = normalizeMetricValue(feedback[metric.key]);
          return (
            <div key={metric.key}>
              <div className="mb-1 flex items-center justify-between text-[11px] text-slate-300">
                <span>{metric.label}</span>
                <span>{Math.round(value * 100)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-800/70">
                <div
                  className="h-1.5 rounded-full bg-sky-300 transition-all duration-300"
                  style={{ width: `${Math.round(value * 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LessonPanel({ skill, lessonState, analysis, comparison, errorMessage }) {
  return (
    <div className="glass rounded-3xl p-5">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Lesson state</div>
      <div className="mt-3 space-y-2 text-sm text-slate-200">
        <div>Mode: {skill}</div>
        <div>Lesson stage: {lessonState.stage}</div>
        <div>
          Measure: {lessonState.measureIndex ?? "—"}
          {lessonState.totalMeasures ? ` / ${lessonState.totalMeasures}` : ""}
        </div>
        {lessonState.prompt ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-slate-100">
            {lessonState.prompt}
          </div>
        ) : null}
      </div>

      {analysis ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
          <div className="font-medium text-white">Phrase analysis</div>
          <div className="mt-1">{analysis.summary}</div>
          {analysis.notes?.length ? (
            <div className="mt-2 text-xs text-slate-300">
              Notes: {analysis.notes.map((note) => note.note_name || note.note || "?").join(", ")}
            </div>
          ) : null}
          <FeedbackMeters title="Phrase feedback" feedback={analysis.performance_feedback} />
        </div>
      ) : null}

      {comparison ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
          <div className="font-medium text-white">Comparison</div>
          <div className="mt-1">{comparison.summary}</div>
          <div className="mt-2 text-xs text-slate-300">
            Accuracy: {Math.round((comparison.accuracy || 0) * 100)}%
          </div>
          <FeedbackMeters title="Calibrated feedback" feedback={comparison.performance_feedback} />
        </div>
      ) : null}

      {errorMessage ? (
        <div className="mt-4 rounded-2xl border border-red-300/30 bg-red-400/10 px-4 py-3 text-sm text-red-100">
          {errorMessage}
        </div>
      ) : null}
    </div>
  );
}

export function SessionLog({ captions }) {
  return (
    <div className="glass rounded-3xl p-5">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Session log</div>
      <div className="mt-4 max-h-[26rem] space-y-3 overflow-y-auto">
        {captions.length ? (
          captions.map((caption) => (
            <div key={caption.id} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                {caption.role}
              </div>
              <div className="mt-1 text-sm text-slate-100">{caption.text}</div>
            </div>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
            Sign in and start with “Prepare lesson” or “Hear phrase”. Live captions and lesson guidance will appear here.
          </div>
        )}
      </div>
    </div>
  );
}
