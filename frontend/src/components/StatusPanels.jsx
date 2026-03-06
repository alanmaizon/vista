const FEEDBACK_METRICS = [
  { key: "pitchAccuracy", label: "Pitch" },
  { key: "rhythmAccuracy", label: "Rhythm" },
  { key: "tempoStability", label: "Tempo" },
  { key: "dynamicRange", label: "Dynamics" },
  { key: "articulationVariance", label: "Articulation" },
];

function normalizeMetricValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(1, numeric));
}

function formatToolCallTime(value) {
  if (!value) {
    return "just now";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "recently";
  }
  const deltaMs = Math.max(0, Date.now() - timestamp);
  const deltaSeconds = Math.round(deltaMs / 1000);
  if (deltaSeconds < 60) {
    return `${deltaSeconds}s ago`;
  }
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`;
  }
  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) {
    return `${deltaHours}h ago`;
  }
  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays}d ago`;
}

function MetricTile({ label, value, tone = "sky" }) {
  const toneClass =
    tone === "emerald"
      ? "from-emerald-400/12 to-emerald-400/4 text-emerald-50"
      : tone === "amber"
        ? "from-amber-300/14 to-amber-300/4 text-amber-50"
        : "from-sky-400/12 to-sky-400/4 text-sky-50";

  return (
    <div className={`rounded-[1.4rem] border border-white/10 bg-gradient-to-br ${toneClass} px-4 py-3`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}

function FeedbackMeters({ title, feedback }) {
  if (!feedback || typeof feedback !== "object") {
    return null;
  }
  return (
    <div className="rounded-[1.6rem] border border-white/10 bg-slate-950/45 px-4 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-300">{title}</div>
      <div className="mt-3 space-y-3">
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
  const accuracyValue = comparison?.accuracy
    ? `${Math.round(comparison.accuracy * 100)}%`
    : analysis?.performance_feedback?.pitchAccuracy
      ? `${Math.round(normalizeMetricValue(analysis.performance_feedback.pitchAccuracy) * 100)}%`
      : "—";
  const consistencyValue = userSkillProfile?.consistency_score
    ? `${Math.round(normalizeMetricValue(userSkillProfile.consistency_score) * 100)}%`
    : "—";

  return (
    <div className="glass rounded-[2rem] p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Analysis</div>
          <div className="mt-1 text-sm text-slate-400">
            Compact lesson feedback, adaptive metrics, and tool telemetry.
          </div>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
          {lessonState.stage}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MetricTile label="Accuracy" value={accuracyValue} />
        <MetricTile
          label="Consistency"
          value={consistencyValue}
          tone={userSkillProfile ? "emerald" : "sky"}
        />
        <MetricTile label="Measure" value={lessonState.measureIndex ?? "—"} />
        <MetricTile
          label="Tool success"
          value={`${Math.round(Number(liveToolMetrics?.overall_success_rate || 0) * 100)}%`}
          tone="amber"
        />
      </div>

      {lessonState.prompt ? (
        <div className="mt-4 rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">
          {lessonState.prompt}
        </div>
      ) : null}

      {analysis ? (
        <div className="mt-4 rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-200">
          <div className="font-medium text-white">Phrase analysis</div>
          <div className="mt-1 text-slate-300">{analysis.summary}</div>
          {analysis.notes?.length ? (
            <div className="mt-2 text-xs text-slate-400">
              {analysis.notes.map((note) => note.note_name || note.note || "?").join(" · ")}
            </div>
          ) : null}
          <div className="mt-4">
            <FeedbackMeters title="Phrase feedback" feedback={analysis.performance_feedback} />
          </div>
        </div>
      ) : null}

      {comparison ? (
        <div className="mt-4 rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-200">
          <div className="font-medium text-white">Comparison</div>
          <div className="mt-1 text-slate-300">{comparison.summary}</div>
          <div className="mt-4">
            <FeedbackMeters title="Bar comparison" feedback={comparison.performance_feedback} />
          </div>
        </div>
      ) : null}

      {Array.isArray(nextDrills) && nextDrills.length ? (
        <div className="mt-4 rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-300">
            Recommended drills
          </div>
          <div className="mt-3 space-y-2">
            {nextDrills.slice(0, 3).map((drill) => (
              <div key={drill.id} className="rounded-2xl border border-white/10 bg-slate-950/45 px-3 py-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-100">{drill.title}</div>
                  <div className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300">
                    {drill.difficulty}
                  </div>
                </div>
                <div className="mt-1 text-xs text-slate-400">{drill.rationale}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 rounded-[1.6rem] border border-white/10 bg-white/5 px-4 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-300">
            Live tool reliability
          </div>
          <div className="text-[11px] text-slate-500">{Number(liveToolMetrics?.total_calls || 0)} calls</div>
        </div>
        {Array.isArray(liveToolMetrics?.metrics) && liveToolMetrics.metrics.length ? (
          <div className="mt-3 space-y-2">
            {liveToolMetrics.metrics.slice(0, 3).map((metric) => (
              <div
                key={`${metric.tool_name}-${metric.source}`}
                className="rounded-2xl border border-white/10 bg-slate-950/45 px-3 py-3 text-xs text-slate-300"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-100">{metric.tool_name}</span>
                  <span className="text-slate-500">{metric.source}</span>
                </div>
                <div className="mt-1">
                  Success {Math.round(Number(metric.success_rate || 0) * 100)}% · Avg {Math.round(Number(metric.avg_latency_ms || 0))}ms
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 text-xs text-slate-400">
            No tool telemetry yet. Run a lesson action to populate this panel.
          </div>
        )}
      </div>

      {tutorPrompt ? (
        <div className="mt-4 rounded-[1.6rem] border border-emerald-300/20 bg-emerald-400/10 px-4 py-3 text-xs text-emerald-50">
          <div className="font-semibold uppercase tracking-[0.14em] text-emerald-100">Tutor context</div>
          <div className="mt-1">{tutorPrompt}</div>
        </div>
      ) : null}

      {errorMessage ? (
        <div className="mt-4 rounded-[1.6rem] border border-red-300/30 bg-red-400/10 px-4 py-3 text-sm text-red-100">
          {errorMessage}
        </div>
      ) : null}
    </div>
  );
}

export function SessionLog({ captions }) {
  return (
    <div className="glass rounded-[2rem] p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Session log</div>
        <div className="text-[11px] text-slate-500">{captions.length} entries</div>
      </div>
      <div className="mt-4 max-h-[28rem] space-y-2 overflow-y-auto pr-1">
        {captions.length ? (
          captions.map((caption) => (
            <div key={caption.id} className="rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                {caption.role}
              </div>
              <div className="mt-1 text-sm text-slate-100">{caption.text}</div>
            </div>
          ))
        ) : (
          <div className="rounded-[1.4rem] border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
            Sign in and prepare a lesson to populate the live log.
          </div>
        )}
      </div>
      {Array.isArray(captions) && captions.length ? (
        <div className="mt-4 text-[11px] text-slate-500">
          Recent call: {formatToolCallTime(captions[captions.length - 1]?.id?.split?.("-")?.[0] ? new Date(Number(captions[captions.length - 1].id.split("-")[0])).toISOString() : null)}
        </div>
      ) : null}
    </div>
  );
}
