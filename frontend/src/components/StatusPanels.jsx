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

export function LessonPanel({
  lessonState,
  analysis,
  comparison,
  userSkillProfile,
  nextDrills,
  tutorPrompt,
  liveToolMetrics,
  errorMessage,
}) {
  return (
    <div className="glass rounded-3xl p-5">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Lesson state</div>
      <div className="mt-3 space-y-2 text-sm text-slate-200">
        <div>Mode: Guided lesson loop</div>
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

      {userSkillProfile ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
          <div className="font-medium text-white">Adaptive profile</div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
            <div>
              Weakest:{" "}
              <span className="font-medium capitalize text-slate-100">
                {String(userSkillProfile.weakest_dimension || "—")}
              </span>
            </div>
            <div>
              Consistency: {Math.round(normalizeMetricValue(userSkillProfile.consistency_score) * 100)}%
            </div>
            <div>
              Practice frequency: {Math.round(normalizeMetricValue(userSkillProfile.practice_frequency) * 100)}%
            </div>
            <div>
              Trend: {Math.round(Number(userSkillProfile.last_improvement_trend || 0) * 100)}
            </div>
          </div>
          {userSkillProfile.rolling_metrics ? (
            <FeedbackMeters title="Rolling metrics" feedback={userSkillProfile.rolling_metrics} />
          ) : null}
        </div>
      ) : null}

      {Array.isArray(nextDrills) && nextDrills.length ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
          <div className="font-medium text-white">Recommended next drills</div>
          <div className="mt-2 space-y-2">
            {nextDrills.slice(0, 3).map((drill) => (
              <div key={drill.id} className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2">
                <div className="text-xs font-semibold text-slate-100">
                  {drill.title}{" "}
                  <span className="ml-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-300">
                    {drill.difficulty}
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-300">{drill.rationale}</div>
                <div className="mt-1 text-xs text-slate-400">{drill.instructions}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {tutorPrompt ? (
        <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-400/10 px-4 py-3 text-xs text-emerald-50">
          <div className="font-semibold uppercase tracking-[0.14em] text-emerald-100">Tutor context</div>
          <div className="mt-1">{tutorPrompt}</div>
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
        <div className="font-medium text-white">Live tool reliability</div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
          <div>Total calls: {Number(liveToolMetrics?.total_calls || 0)}</div>
          <div>
            Success: {Math.round(Number(liveToolMetrics?.overall_success_rate || 0) * 100)}%
          </div>
          <div>Successes: {Number(liveToolMetrics?.total_successes || 0)}</div>
          <div>Failures: {Number(liveToolMetrics?.total_failures || 0)}</div>
        </div>
        {Array.isArray(liveToolMetrics?.metrics) && liveToolMetrics.metrics.length ? (
          <div className="mt-3 space-y-2">
            {liveToolMetrics.metrics.slice(0, 4).map((metric) => (
              <div
                key={`${metric.tool_name}-${metric.source}`}
                className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2 text-xs text-slate-300"
              >
                <div className="font-semibold text-slate-100">
                  {metric.tool_name} <span className="text-slate-400">({metric.source})</span>
                </div>
                <div className="mt-1">
                  Calls: {metric.total_calls} | Success: {Math.round(Number(metric.success_rate || 0) * 100)}% |
                  Avg latency: {Math.round(Number(metric.avg_latency_ms || 0))}ms
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-400">
            No live tool telemetry yet. Run a lesson action to populate this panel.
          </div>
        )}
      </div>

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
            Sign in and start with “Prepare lesson”. Use “Capture phrase” or “Read from camera” as helper actions in the same loop.
          </div>
        )}
      </div>
    </div>
  );
}
